# Summary of `T.rd` `README.md` documentation

`README.md` is a short advertisement followed by an instruction manual:
the intro, Quick Start, Download Prompt, Enabling `EZPkg` for Your
Program, Choosing Versions, Releasing a Program (email the `.py`,
`zipapp`, `uv`), How `EZPkg` Actually Works (one bullet per bootstrap
stage) and the Conclusion.  Both bootstrap copies are `nopip5`, and
tests keep them equal to `quick_start.py`.  The last proposals (stderr
for `pip`'s output, the `stdout=2` bullet, and step 4 catching imports
your own Python happens to have) were applied on 2026-10-12.  No
`Claude:` or `Issue:` comments remain.  Wayne will redo the intro and
do his own end-to-end reads; the Quick Start works only once `ezpkg` is
on PyPI (task 7).

Reopened on 2026-10-13 for Wayne's read before the test.pypi upload
(`T.utt`): he edited the README text and added "Do not edit try block!"
comments to the bootstrap.  Those are comments only, so it is still
`nopip5` with the same fingerprint; all four copies agree.
