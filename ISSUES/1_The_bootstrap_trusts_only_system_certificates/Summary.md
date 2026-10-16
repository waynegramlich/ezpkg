# Summary of `I.btosc` The bootstrap trusts only system certificates

Fixed 2026-10-16 by `nopip6`.  A GitHub macOS runner confirmed the
fear: python.org's 3.15.0, before `Install Certificates.command`, has
no certificates (`cafile=None`), and `nopip5` stopped at once with
`ezpkg: choose pip failed: URLError(SSLCertVerificationError(...
CERTIFICATE_VERIFY_FAILED ...))`.  `nopip6` fetches through `def g(u)`:
`urlopen`, else `curl -fsSL` (every Mac has `/usr/bin/curl`, which
uses the Keychain), else the `urllib` error as before.  Once `pip` has
arrived nothing else needs Python's certificates, since `pip` brings
its own.  `check.yml`'s `python-org` job (python.org 3.14.8 and
3.15.0, no certificates) passed in run 38977835683, and now guards it.
Chad's old Mac had worked with `nopip5`, so its Python had
certificates.  Related: `T.gar`, `T.towam`, `I.wmau`.
