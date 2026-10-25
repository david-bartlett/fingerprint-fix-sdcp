# Build-time fixes

`install.sh` applies every `*.patch` file in this folder to the fetched
libfprint-egismoc-sdcp source before building — but only while the source still
needs it:

- the patch applies → it is applied, and recorded in the install marker
- the patch is already in the source (it applies in reverse) → skipped
- the patch has a `Needed-if-source-has: <file>|<text>` line and that text is
  no longer in the file (upstream fixed it a different way) → skipped
- otherwise the install stops, so an out-of-date fix is never built silently

Put a `Subject:` line at the top (shown by the installer), then the reason,
then the `git diff`. Remove the file once the fix is in the fork.

No fixes are needed at the moment.
