# 1 The bootstrap trusts only system certificates

Case 13 reaches PyPI with `urllib`, which verifies against the operating
system's certificate store, where case 7 handed the whole fetch to `pip` and
its own bundled store.  Linux distributions provide one. The python.org
installer for macOS does not until its `Install Certificates.command` has been
run, so there the bootstrap would fail on its first request.  Untested; nobody
here has a Mac.

Various thoughts:
* Wayne (2026-10-01): I'm working on getting access to macOS and
  Windows machines, so that is in progress.
* Claude (2026-10-01): Simulated on Linux by pointing `SSL_CERT_FILE`
  at an empty file, and at no file, with `SSL_CERT_DIR` gone too.
  `nopip3` stops at once with one line, exit status 1: `cannot fetch
  alt_venv, choose pip failed: URLError(SSLCertVerificationError(1,
  '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable
  to get local issuer certificate ...'))`.  That is the very text a
  python.org macOS install prints without its certificates, and it
  leads anyone who searches for it to `Install Certificates.command`,
  so a hint in the paste would cost a line to say what the message
  already says.  What a real Mac adds is whether it fails this way at
  all.
