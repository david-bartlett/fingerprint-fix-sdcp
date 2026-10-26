# fingerprint-fix-sdcp for Fedora
#
# Build with packaging/rpm/build.sh, which makes the two source tarballs and
# passes VERSION and DRIVER from the repository:
#   --define "fixver 1.0.1" --define "driver <full commit id>"

%{!?fixver: %global fixver 0}
%{!?driver: %global driver 0}
%{!?rel:    %global rel 1}

%global pkglibdir  %{_prefix}/lib/fingerprint-fix-sdcp
%global scriptdir  %{_libexecdir}/fingerprint-fix-sdcp
%global boot_check samsung-galaxybook-fprint-sdcp-boot-check.service
%global user_check samsung-galaxybook-fprint-sdcp-user-check.timer
%{!?_unitdir:       %global _unitdir       %{_prefix}/lib/systemd/system}
%{!?_userunitdir:   %global _userunitdir   %{_prefix}/lib/systemd/user}
%{!?_presetdir:     %global _presetdir     %{_prefix}/lib/systemd/system-preset}
%{!?_userpresetdir: %global _userpresetdir %{_prefix}/lib/systemd/user-preset}

# A private copy of libfprint, loaded by fprintd only: it must not provide
# libfprint-2.so.2 to other packages, nor make sensor-check depend on it.
%global __provides_exclude_from ^%{pkglibdir}/.*$
%global __requires_exclude ^libfprint-2\\.so\\.2.*$
%global debug_package %{nil}

Name:           fingerprint-fix-sdcp
Version:        %{fixver}
Release:        %{rel}%{?dist}
Summary:        Egis fingerprint reader fix for Samsung Galaxy Book, with a Fingerprint Manager
License:        GPL-2.0-or-later AND LGPL-2.1-or-later
URL:            https://github.com/david-bartlett/fingerprint-fix-sdcp
Source0:        %{name}-%{version}.tar.gz
Source1:        https://github.com/david-bartlett/libfprint-egismoc-sdcp/archive/%{driver}/libfprint-egismoc-sdcp-%{driver}.tar.gz
ExclusiveArch:  x86_64

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  patch
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(gusb)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  systemd-rpm-macros

# The distro's fprintd and libfprint stay installed: fprintd is only pointed at
# this driver with a drop-in.
Requires:       fprintd
Requires:       fprintd-pam
Requires:       libfprint
Requires:       glib2
Requires:       libnotify
Requires:       usbutils
Requires:       polkit
Requires:       python3
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk3
%{?systemd_requires}

%description
Makes the Egis match-on-chip fingerprint reader (1c7a:05a5 on Galaxy Book 4 /
Book 5 Pro, 1c7a:05a1 on Book 3 / Book 4) work on Linux. Builds only the
egismoc SDCP driver of libfprint and points fprintd at it; the distro's
libfprint is not replaced. Includes a monitor and boot-time check that warn
when the sensor loses a fingerprint (e.g. after booting Windows), sharing
enrolments between installs, and the Galaxy Book Fingerprint Manager.

%prep
%setup -q -a 1

%build
%{?set_build_flags}
bash packaging/build-driver.sh libfprint-egismoc-sdcp-%{driver}

%install
FIX_PACKAGE_SCRIPT_DIR=%{scriptdir} \
    bash packaging/install-files.sh %{buildroot} libfprint-egismoc-sdcp-%{driver} \
        %{version}-%{release} rpm
# Enabled at install: the boot check, and the login check for every user.
install -d %{buildroot}%{_presetdir} %{buildroot}%{_userpresetdir}
echo "enable %{boot_check}" > %{buildroot}%{_presetdir}/80-fingerprint-fix-sdcp.preset
echo "enable %{user_check}" > %{buildroot}%{_userpresetdir}/80-fingerprint-fix-sdcp.preset

%pre
# First install over a copy made by install.sh: remove that copy (its own
# cleanup; enrolled fingerprints are kept), or its drop-in in /etc would
# override this package's.
if [ "$1" -eq 1 ] && [ -f /etc/samsung-galaxybook-egismoc-sdcp.installed ] \
        && [ -x /usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh ]; then
    echo "Removing the copy of fingerprint-fix-sdcp installed with install.sh (fingerprints are kept)"
    /usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh || :
fi

%post
%systemd_post %{boot_check}
%systemd_user_post %{user_check}
# fprintd picks up the drop-in now; the drop-in changes its environment, so
# reload first (systemd's own reload runs at the end of the transaction).
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart fprintd.service >/dev/null 2>&1 || :
# What the distro libfprint looked like, so the monitor tests it again only
# once it changes.
if [ ! -f /var/lib/samsung-galaxybook/libfprint-system.sha256 ]; then
    lib=$(ldconfig -p 2>/dev/null | grep 'libfprint-2\.so\.2 ' | awk '{print $NF}' | head -1)
    if [ -n "$lib" ]; then
        mkdir -p /var/lib/samsung-galaxybook
        sha256sum "$lib" | awk '{print $1}' > /var/lib/samsung-galaxybook/libfprint-system.sha256
    fi
fi
if [ "$1" -eq 1 ]; then
    echo "Open 'Galaxy Book Fingerprint Manager' from the app menu to enrol a finger"
    echo "and turn on fingerprint login."
    # The same hint as a notification now, for anyone logged into a desktop.
    %{scriptdir}/notify-users.sh || :
fi

%preun
%systemd_preun %{boot_check}
%systemd_user_preun %{user_check}

%postun
if [ "$1" -eq 0 ]; then
    rm -f /run/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf
fi
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart fprintd.service >/dev/null 2>&1 || :

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{pkglibdir}/
%{scriptdir}/
%dir %{_unitdir}/fprintd.service.d
%{_unitdir}/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf
%{_unitdir}/samsung-galaxybook-fprint-sdcp-monitor.service
%{_unitdir}/%{boot_check}
%{_userunitdir}/samsung-galaxybook-fprint-sdcp-user-check.service
%{_userunitdir}/%{user_check}
%{_userunitdir}/samsung-galaxybook-session.target
%{_presetdir}/80-fingerprint-fix-sdcp.preset
%{_userpresetdir}/80-fingerprint-fix-sdcp.preset
%config(noreplace) %{_sysconfdir}/xdg/autostart/fingerprint-fix-sdcp-session.desktop
%{_datadir}/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules
%{_datadir}/polkit-1/actions/io.github.david-bartlett.galaxybook-fingerprint-manager.policy
%{_datadir}/applications/io.github.david_bartlett.GalaxyBookFingerprintManager.desktop
%{_datadir}/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg
%{_bindir}/galaxybook-fingerprint-manager
