# Summary of `I.htdwcp` How to deal with compiled packages

Answered 2026-10-22 by what `T.ee` built.  The `email` and `uv` release
forms carry compiled packages for every computer: `uv` resolves for
all platforms, and the `email` copy's `checksums` approve each
package's wheel, a compiled one by version with its `tag:`.  A
`zipapp` carries pure Python only: a compiled package this computer
needs stops it, and one only another computer needs (such as Windows'
`pywin32`) is a release warning.  Approvals are no longer only the
author's machine's.  README "Releasing a Packaged Program" says which
form to use.  Related: `T.ee`.
