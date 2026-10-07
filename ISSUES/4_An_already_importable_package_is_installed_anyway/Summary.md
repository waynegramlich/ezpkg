# Summary of `I.apiia` An already-importable package is installed anyway

Rejected: All twelve cases ask whether the package is on disk at their own
target, never whether it is already importable.  With `coverage` present in an
active virtual environment, a case spends 1.42 s and 1.8 MB installing a copy
it will not use, where a leading `try: import` costs 0.10 s.  Cheap to fix;
deliberately not fixed yet.

Last thought: Wayne (2026-10-01): Rejected. I don't care if an extra download
occurs.
