# Supported hardware

[← Back to the README](../README.md)

Which Galaxy Book models and distros are confirmed working, test details for each reader, and which models are refused.

**Confirmed working:** Galaxy Book5 Pro 14" (940XHA, reader `05a5`) on Fedora 45, Ubuntu 26.04, Linux Mint 22.3 and 27, MX Linux 25 and CachyOS; Galaxy Book4 (reader `05a1`) on Zorin OS 18, and Galaxy Book4 Ultra (960XGL, reader `05a1`) on Ubuntu 26.04. Find your reader with `lsusb | grep 1c7a`.

## Test details by reader

| USB ID | Galaxy Book Model | Status |
| --- | --- | --- |
| `1c7a:05a5` | Galaxy Book4 / Book5 Pro | **Confirmed working** on Galaxy Book5 Pro 14" (940XHA): Fedora 45, Linux Mint 27 (beta), Linux Mint 22.3 (OpenSSL 3.0.13 — needs commit 3b0ee1f or later), Ubuntu 26.04, MX Linux (Xfce) and CachyOS (KDE), 2026-10-24/25 |
| `1c7a:05a1` | Galaxy Book4 (ETU905A80-E) | **Confirmed working** on a Galaxy Book4 by [@gabaritei88](https://github.com/gabaritei88): Zorin OS 18.1 (OpenSSL 3.0.13 — needs commit 3b0ee1f or later), keeping the 4 Windows Hello templates on the sensor, 2026-10-26. On a Galaxy Book4 Ultra (960XGL) by [@Andycodeman](https://github.com/Andycodeman), thanks: Ubuntu 26.04 with the 2.13.6 packages, 2026-11-09 |

The **Galaxy Book3** can have the `05a1` reader too, but nobody has tested this fix on one, so `install.sh`, the `.rpm`, the `.deb` and the Arch `PKGBUILD` refuse to install there (a Book3 is recognised by its model name, or by `F` as the letter after `X` or `Q` in its model code, e.g. `940XFG`. Most Book4 models have `G` there and the Book5 has `H`, e.g. `960XGL` and `940XHA`, but the letter isn't always the generation: the Galaxy Book2 Pro SE is `950XGK`). To try it anyway: `FPRINT_SDCP_FORCE=1`. If it works on your Book3, please tell us with the form below.

The **Galaxy Book2 Pro SE** (`950XGK`) has the `05a1` reader too. It's [reported working](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp/issues/4) on Ubuntu 26.04 with the same driver this fix builds, but nobody has tested this fix's packages on it. They don't refuse to install there.

Only 64-bit Intel/AMD (`x86_64`) Galaxy Books are supported. The ARM-based **Galaxy Book4 Edge** (Snapdragon) isn't: every install method refuses on an ARM processor.

Got it working on a model or distro not listed here? Please tell us with the [**It works on my laptop / distro**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=works_on.yml) form — that's how this list grows.
