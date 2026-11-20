# Security

fingerprint-fix-sdcp installs a fingerprint driver, a helper that runs as root, and changes to how you log in. If you find a way it could be misused, such as getting past fingerprint login, reading or replacing someone's fingerprint records, or running something as root that it shouldn't, please tell us privately first.

## How to report

- **Use GitHub's private reporting:** on this repository's **Security** tab, choose **Report a vulnerability**. Only you and the maintainer can see the report.
- Please **don't open a public issue** with the details until a fix is released.
- Say which version you have (the Manager's About box, or `rpm -q fingerprint-fix-sdcp` / `dpkg -s fingerprint-fix-sdcp` / `pacman -Q fingerprint-fix-sdcp`), your laptop model and reader (`lsusb | grep 1c7a`), your distro, and the steps that show the problem.

You'll get a reply as soon as possible, usually within a few days. When it's fixed, the release notes say so, with credit to you if you'd like it.

## Which versions

Only the newest release gets fixes. Update first and check the problem is still there: the Manager's ☰ → *Check for new versions*, or see [Updating](docs/updating.md).

## What's covered elsewhere

- **The SDCP protocol and the driver itself** (certificate and attestation checks, the session secret) come from [libfprint-egismoc-sdcp](https://github.com/david-bartlett/libfprint-egismoc-sdcp). Report problems in the driver code there too, or here if you're not sure. Its known limits are listed in [How it works → Security notes](docs/how-it-works.md#security-notes-from-upstream).
- **fprintd, PAM and your distro's libfprint** belong to their own projects.
