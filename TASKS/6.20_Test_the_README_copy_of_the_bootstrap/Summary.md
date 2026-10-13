# Summary of `T.trcb` Test the README copy of the bootstrap

`BootstrapCheckTest.test_the_enabling_copy_is_current` takes the first
Python block under README "Enabling `AltVEnv` for Your Program" and
fails unless its Part 2 import lines (between the `# Part 2:` and
`# Part 3:` comments) equal `quick_start.py`'s, in order, and its
bootstrap, found by `find_bootstrap`, has the same
`bootstrap_fingerprint`.  Part 1 and the docstring are placeholders
there and are not compared.  Checked by mutation on 2026-10-12: a
stale `bootstrap="nopip3"` and a dropped `import json` each fail it.
The heading is matched literally, so the rename (`T.rp`) must update
the test with the heading.  Related: `T.rd`, `T.rp`.
