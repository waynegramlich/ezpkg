# Summary of `I.wtmifs` The wheel tag matcher is a five-line stand-in

Cases 3 and 12 pick wheels with a substring test that cannot tell musl from
glibc, and does not read the glibc version a manylinux tag encodes.  It agreed
with pip for one package on one platform.  On Alpine it would download a
manylinux wheel and fail at import with a loader error.  The matcher is also
written out twice, once per case, so a correction has to be made in both
places.

Last thought: Claude (2026-10-01): Closed with Wayne's agreement. The matcher
lives only in `nopip1` and `nopip2`, which are measurement and will not ship;
`nopip3` leaves choosing wheels to `pip`. The abi3 and musl faults are real but
can no longer reach a stranger.
