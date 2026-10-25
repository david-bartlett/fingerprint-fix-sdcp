#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — test Abdallah's newest driver before syncing the fork
# =============================================================================
# For the maintainer of the david-bartlett/libfprint-egismoc-sdcp fork.
# Compares abdallah-alkanani/libfprint-egismoc-sdcp (egismoc-sdcp) with the
# fork. If upstream has something newer, installs that build on this laptop so
# it can be tested before clicking "Sync fork" on GitHub (syncing publishes it
# to everyone who installs). Enrolled fingerprints are kept.
#
#   bash tools/test-latest-libfprint.sh      (asks for sudo for the install)
# =============================================================================
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL="$DIR/../install.sh"
[ -f "$INSTALL" ] || { echo "Installer not found: $INSTALL — keep the repository folder together."; exit 1; }
INSTALL="$(cd "$(dirname "$INSTALL")" && pwd)/install.sh"
UPSTREAM=https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp.git
FORK=https://github.com/david-bartlett/libfprint-egismoc-sdcp.git

up=$(git ls-remote "$UPSTREAM" refs/heads/egismoc-sdcp | cut -c1-12)
fork=$(git ls-remote "$FORK" refs/heads/egismoc-sdcp | cut -c1-12)
echo "Upstream: $up   Your fork: $fork"
if [ "$up" = "$fork" ]; then
    echo "Your fork is already up to date — nothing new to test."
    exit 0
fi

echo "Testing upstream $up …"
sudo SDCP_REPO_URL="$UPSTREAM" bash "$INSTALL"
echo
echo "If fprintd-verify works: click 'Sync fork' on GitHub, then rerun"
echo "  sudo bash $INSTALL"
echo "to go back to the fork's build (enrolments are kept)."
