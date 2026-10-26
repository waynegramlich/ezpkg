# LLM Agent Context Log

## 2026-10-26, Wayne's decisions (in chat)

Grew out of `I.mlmfpn~26`.  A name shared with a PyPI package does not
matter beyond the development question (`EZPkg.choose`): an `email` or
`uv` release can only mean PyPI's (the program's own modules make
`local_imports` refuse them, since each is a single script), and a
`zipapp` carries the program's own modules, whose copies come first on
the recipient's `sys.path`.  No extra notice about the clash, in
development or at release.

To build (not built yet):
* a. `local` names are found where the program's run imported them
  from; one never imported stops the release, saying so.
* b. The program's own modules are followed recursively (`helper.py`
  importing `util.py`).
* c. Their imports are scanned too, so the packages they need must be
  in Part 1, as `prog.py`'s must.
* d. A directory module goes in whole, without `__pycache__/`.
* The release asks nothing (a release is a run with a new `version`).
  It prints the carried files as an indented list, by who imports
  whom, each listed once at its first place; the same list goes into
  the release's `prog.py.releases` entry.
* `local_imports` then refuses only `email` and `uv`, and its refusal
  shows the same indented list.

Order: close `I.mlmfpn` and release it as 0.0.5 first; this follows in
a later release.

Also: the recursive scan of the program's own modules should run
`refuse_shadowing`'s check on their imports too (`I.mlmfpn~26`).
