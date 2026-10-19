# Summary of `I.uedepi` A uv export drops an ezpkg the program imports

Fixed 2026-10-17 by `T.eui`: `for_export` keeps `ezpkg` in a `uv` or
`zipapp` export when the program (bootstrap taken out) imports it, and
refuses the export if the approvals do not pin it; test
`test_an_export_keeps_an_ezpkg_the_program_imports`.  The release
(`T.abfd` slice 5) now makes the exports.  Wayne's dogfood of the
exports is a `ux/drive.py` step.
