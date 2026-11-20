# Contributing

Thanks for helping. The most useful things, in order:

1. **Tell us it works on your laptop:** the [**It works on my laptop / distro**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=works_on.yml) form. That's how [Supported hardware](docs/supported-hardware.md) grows.
2. **Report a problem:** the [**Bug report**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=bug_report.yml) form, which asks for the logs that usually save a round of questions. Security problems: [SECURITY.md](SECURITY.md) instead, privately.
3. **Send a fix or a feature** as a pull request.

## Pull requests

- **Read [PLAN.md](PLAN.md) first.** It explains how the project works, every file, the safety rules (§10: the helper runs as root and the sensor holds real fingerprints) and how to test without the hardware (§9.1).
- **One topic per pull request,** from its own branch, against `main`.
- **Add a line under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md)** for anything users will notice, and update `README.md` or `docs/` where they describe what you changed.
- **Add a short note to [`handoff/`](handoff/README.md)** saying what changed and what the next person needs to know.
- **Say how you tested it** and what you couldn't test, especially on which laptop, reader and distro.
- **Don't change `VERSION` or `DRIVER`,** or make tags or releases: the maintainer releases after testing on his own laptop.

## Using AI tools

Welcome, as long as you understand the change and have tested it. Say so in the pull request, for example with an `Assisted-by:` or `Co-Authored-By:` line in the commit message. Much of this project is written that way too: see [How it's built and tested](README.md#how-its-built-and-tested). Coding agents should read [AGENTS.md](AGENTS.md).

## Style

British English. The app is "Galaxy Book Fingerprint Manager" the first time, then "the Manager".
