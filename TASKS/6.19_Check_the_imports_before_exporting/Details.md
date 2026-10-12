# 6.19 Check the imports before exporting

Before any `ALT_VENV_EXPORT` writes anything, read the program's
`import` statements and refuse the export if one of them is not
covered by Part 1.  The case it catches: a package that the author's
own Python happens to have (a Linux distribution's `python3-requests`,
say) works on the author's machine without being in `dependencies`,
and then fails on the machine the program is sent to.  Asking "is this
package preinstalled?" has no stable answer across machines, so the
check happens when the program leaves instead.
