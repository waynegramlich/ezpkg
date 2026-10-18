# 22 A failed fetch shows the pip output

Any failed fetch reaches the person running the program as `ezpkg:
fetch packages failed: RuntimeError('<pip's text>')`, which is `pip`'s
own output, warnings included.  The goal (Wayne, 2026-10-17): never put
the problem on the end user's plate.  The most they should ever see is
`EZPkg`'s prompts before the program's own code runs.  Found while
dogfooding `T.kdaiis`: an approvals file pinning a test.pypi.org
`ezpkg` that pypi.org lacks gave `ResolutionImpossible`, after an
unrelated `.egg` DEPRECATION line from the machine's own packages.
That cause was the dogfood harness, since fixed, but the message is
real.

Cases a stranger could meet:
1. No network, on a first run or later.
2. A version the approvals pin that the index no longer has (yanked
   or deleted).
3. No wheel for their machine, such as a compiled package with no
   build for their platform or Python (`I.htdwcp`).
4. Noise from their own Python, such as `pip`'s `.egg` DEPRECATION
   warning, ahead of the real reason.
5. No private `pip`: when `ezpkg` is already importable (`pip install
   ezpkg`, `uv run`), the bootstrap never fetches `pip.whl`, so
   `EZPkg.pip` falls back to the interpreter's own `pip`, perhaps old
   or missing.  Seen with the system's `pip` 24.0: `fetching without the
   program's exclude-newer date ..., which this index or pip cannot
   apply`, and the `.egg` warning of case 4.  Proposed: `EZPkg` fetches
   its own `pip.whl` whenever it has none, as the bootstrap does.

Each needs one plain `ezpkg:` line, with `pip`'s text kept only for
the author.  Test cases that provoke each of `pip`'s errors come
first.  Needed before `T.utpat`.
