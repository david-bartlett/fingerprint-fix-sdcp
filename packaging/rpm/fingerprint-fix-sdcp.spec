# fingerprint-fix-sdcp for Fedora — two packages from one spec:
#   fingerprint-fix-sdcp            the egismoc SDCP driver for fprintd (x86_64)
#   galaxybook-fingerprint-manager  the Fingerprint Manager, its monitor and
#                                   boot / login checks (noarch)
# The driver recommends the same version of the Manager (dnf installs it too,
# unless told not to); either works without the other: the driver alone (enrol
# in the desktop's settings), or the Manager alone with the distro's libfprint
# once it has SDCP. Each can be removed alone.
#
# Build with packaging/rpm/build.sh, which makes the two source tarballs and
# passes VERSION and DRIVER from the repository:
#   --define "fixver 1.0.1" --define "driver <full commit id>"

%{!?fixver: %global fixver 0}
%{!?driver: %global driver 0}
%{!?rel:    %global rel 1}

%global pkglibdir    %{_prefix}/lib/fingerprint-fix-sdcp
%global scriptdir    %{_libexecdir}/fingerprint-fix-sdcp
%global mgrname      galaxybook-fingerprint-manager
%global mgrdir       %{_prefix}/lib/%{mgrname}
%global mgrscriptdir %{_libexecdir}/%{mgrname}
%global boot_check   samsung-galaxybook-fprint-sdcp-boot-check.service
%global user_check   samsung-galaxybook-fprint-sdcp-user-check.timer
%global fix_update   fingerprint-fix-sdcp-update-check.timer
%global mgr_update   galaxybook-fingerprint-manager-update-check.timer
%{!?_unitdir:       %global _unitdir       %{_prefix}/lib/systemd/system}
%{!?_userunitdir:   %global _userunitdir   %{_prefix}/lib/systemd/user}
%{!?_presetdir:     %global _presetdir     %{_prefix}/lib/systemd/system-preset}
%{!?_userpresetdir: %global _userpresetdir %{_prefix}/lib/systemd/user-preset}

# A private copy of libfprint, loaded by fprintd only: it must not provide
# libfprint-2.so.2 to other packages.
%global __provides_exclude_from ^%{pkglibdir}/.*$
%global __requires_exclude ^libfprint-2\\.so\\.2.*$
%global debug_package %{nil}

Name:           fingerprint-fix-sdcp
Version:        %{fixver}
Release:        %{rel}%{?dist}
Summary:        Egis fingerprint reader driver for Samsung Galaxy Book (egismoc SDCP, for fprintd)
License:        GPL-2.0-or-later AND LGPL-2.1-or-later
URL:            https://github.com/david-bartlett/fingerprint-fix-sdcp
Source0:        %{name}-%{version}.tar.gz
Source1:        https://github.com/david-bartlett/libfprint-egismoc-sdcp/archive/%{driver}/libfprint-egismoc-sdcp-%{driver}.tar.gz
ExclusiveArch:  x86_64

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  patch
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(gusb)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  systemd-rpm-macros

# The distro's fprintd and libfprint stay installed: fprintd is only pointed at
# this driver with a drop-in. The Manager (window, monitor, boot and login
# checks) is recommended, not required: dnf installs it too unless told not
# to, and either package works without the other.
Recommends:     %{mgrname} = %{version}-%{release}
Requires:       fprintd
Requires:       fprintd-pam
Requires:       libfprint
Requires:       glib2
Requires:       usbutils
%{?systemd_requires}

%description
Makes the Egis match-on-chip fingerprint reader (1c7a:05a5 on Galaxy Book4 /
Book5 Pro, 1c7a:05a1 on Book4) work on Linux. Builds only the egismoc SDCP
driver of libfprint and points fprintd at it; the distro's libfprint is not
replaced. Turns fingerprint login on at the first install. The Galaxy Book
Fingerprint Manager (galaxybook-fingerprint-manager) is recommended with it, but
the driver works on its own: enrol in your desktop's settings.

%package -n %{mgrname}
Summary:        Galaxy Book Fingerprint Manager, with boot-time and login checks
BuildArch:      noarch
Requires:       fprintd
Requires:       fprintd-pam
Requires:       libfprint
Requires:       libnotify
Requires:       usbutils
Requires:       polkit
Requires:       python3
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk3
%{?systemd_requires}

%description -n %{mgrname}
Test, enrol, export / import and tidy fingerprints on the Samsung Galaxy Book's
Egis fingerprint reader, with a monitor and boot-time check that warn when the
sensor loses a fingerprint (e.g. after booting Windows). Works with
fingerprint-fix-sdcp's driver, or with the distro's own libfprint once it has
SDCP support. Installed alone it uses whichever driver fprintd has.

%prep
%setup -q -a 1

%build
%{?set_build_flags}
bash packaging/build-driver.sh libfprint-egismoc-sdcp-%{driver}

%install
FIX_PACKAGE_SCRIPT_DIR=%{scriptdir} MGR_PACKAGE_SCRIPT_DIR=%{mgrscriptdir} \
    bash packaging/install-files.sh %{buildroot} libfprint-egismoc-sdcp-%{driver} \
        %{version}-%{release} rpm driver
FIX_PACKAGE_SCRIPT_DIR=%{scriptdir} MGR_PACKAGE_SCRIPT_DIR=%{mgrscriptdir} \
    bash packaging/install-files.sh %{buildroot} libfprint-egismoc-sdcp-%{driver} \
        %{version}-%{release} rpm manager
# Enabled at install: the boot check, and the login check for every user.
install -d %{buildroot}%{_presetdir} %{buildroot}%{_userpresetdir}
echo "enable %{boot_check}" > %{buildroot}%{_presetdir}/80-%{mgrname}.preset
printf 'enable %%s\n' %{user_check} %{mgr_update} > %{buildroot}%{_userpresetdir}/80-%{mgrname}.preset
# The driver's hourly release check (skipped while the Manager is installed).
echo "enable %{fix_update}" > %{buildroot}%{_userpresetdir}/80-%{name}.preset

%pre
# Only for a Galaxy Book4 / Book5 with the Egis reader (USB 1c7a:05a5 / 05a1):
# elsewhere fprintd needs the distro's drivers. Same rule as fprintd-env.sh.in,
# install.sh and the Manager. Prints why not, and fails, on other hardware.
fix_hardware_problem() {
    # 64-bit Intel/AMD only: not ARM, e.g. the Snapdragon Galaxy Book4 Edge.
    case "$(uname -m)" in
        x86_64) ;;
        *) echo "this computer's processor is $(uname -m), not 64-bit Intel/AMD (x86_64)"
           return 1 ;;
    esac
    _vendor=$(cat /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/board_vendor 2>/dev/null | tr '[:upper:]' '[:lower:]')
    case "$_vendor" in
        *samsung*) ;;
        *) echo "this computer is not a Samsung (vendor: $(head -n1 /sys/class/dmi/id/sys_vendor 2>/dev/null || echo unknown))"
           return 1 ;;
    esac
    # Galaxy Book3 laptops can have the same 1c7a:05a1 reader as the Book4, but
    # this fix is only tested on the Book4 and Book5: refused there. Recognised
    # by the family name, or the model code: NP / 3 digits / X (laptop) or Q
    # (360) / generation letter, F = Book3 (G = Book4, H = Book5).
    _family=$(cat /sys/class/dmi/id/product_family 2>/dev/null)
    _model=$(cat /sys/class/dmi/id/product_name 2>/dev/null)
    if echo "$_family" | grep -Eqi 'galaxy ?book ?3($|[^0-9])' \
            || echo "$_model" | grep -Eqi '^(NP)?[0-9]{3}[XQ]F'; then
        echo "this is a Galaxy Book3 (${_family:-model $_model}), which this fix isn't tested on"
        return 1
    fi
    for _d in /sys/bus/usb/devices/*; do
        [ "$(cat "$_d/idVendor" 2>/dev/null)" = 1c7a ] || continue
        case "$(cat "$_d/idProduct" 2>/dev/null)" in 05a5|05a1) return 0 ;; esac
    done
    echo "that reader was not found on this computer"
    return 1
}
if [ "$1" -eq 1 ]; then
    if [ "${FPRINT_SDCP_FORCE:-0}" != 1 ] && ! _why=$(fix_hardware_problem); then
        cat >&2 <<EOF

fingerprint-fix-sdcp is only for the Samsung Galaxy Book4 and Book5 (64-bit
Intel/AMD) with the Egis fingerprint reader (USB 1c7a:05a5 or 1c7a:05a1),
but $_why.
Nothing was installed: any other fingerprint reader works with your distro's
own driver. To install anyway (e.g. building a system image for a Galaxy Book):
  sudo FPRINT_SDCP_FORCE=1 dnf install ./fingerprint-fix-sdcp-*.rpm ./galaxybook-fingerprint-manager-*.rpm

EOF
        exit 1
    fi
fi
# First install over a copy made by install.sh: remove that copy with its own
# cleanups (driver, then Manager; enrolled fingerprints are kept), or its
# drop-in in /etc would override this package's. Before 2.0.0 one cleanup
# removed everything.
if [ "$1" -eq 1 ]; then
    # The cleanups delete the libfprint hash that marks an earlier install:
    # note it, so the Manager's %post leaves fingerprint login as it was.
    if [ -x /usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh ] \
            || [ -x /usr/local/bin/galaxybook-fingerprint-manager-cleanup.sh ]; then
        mkdir -p /var/lib/samsung-galaxybook
        touch /var/lib/samsung-galaxybook/keep-pam-setting
    fi
    for c in /usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh \
             /usr/local/bin/galaxybook-fingerprint-manager-cleanup.sh; do
        if [ -x "$c" ]; then
            echo "Removing the copy of fingerprint-fix-sdcp installed with install.sh (fingerprints are kept)"
            "$c" || :
        fi
    done
    [ -f /usr/local/share/icons/hicolor/icon-theme.cache ] && command -v gtk-update-icon-cache >/dev/null 2>&1 \
        && gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || :
fi

%pre -n %{mgrname}
# Only for a Galaxy Book4 / Book5 with the Egis reader (USB 1c7a:05a5 / 05a1):
# elsewhere fprintd needs the distro's drivers. Same rule as fprintd-env.sh.in,
# install.sh and the Manager. Prints why not, and fails, on other hardware.
fix_hardware_problem() {
    # 64-bit Intel/AMD only: not ARM, e.g. the Snapdragon Galaxy Book4 Edge.
    case "$(uname -m)" in
        x86_64) ;;
        *) echo "this computer's processor is $(uname -m), not 64-bit Intel/AMD (x86_64)"
           return 1 ;;
    esac
    _vendor=$(cat /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/board_vendor 2>/dev/null | tr '[:upper:]' '[:lower:]')
    case "$_vendor" in
        *samsung*) ;;
        *) echo "this computer is not a Samsung (vendor: $(head -n1 /sys/class/dmi/id/sys_vendor 2>/dev/null || echo unknown))"
           return 1 ;;
    esac
    # Galaxy Book3 laptops can have the same 1c7a:05a1 reader as the Book4, but
    # this fix is only tested on the Book4 and Book5: refused there. Recognised
    # by the family name, or the model code: NP / 3 digits / X (laptop) or Q
    # (360) / generation letter, F = Book3 (G = Book4, H = Book5).
    _family=$(cat /sys/class/dmi/id/product_family 2>/dev/null)
    _model=$(cat /sys/class/dmi/id/product_name 2>/dev/null)
    if echo "$_family" | grep -Eqi 'galaxy ?book ?3($|[^0-9])' \
            || echo "$_model" | grep -Eqi '^(NP)?[0-9]{3}[XQ]F'; then
        echo "this is a Galaxy Book3 (${_family:-model $_model}), which this fix isn't tested on"
        return 1
    fi
    for _d in /sys/bus/usb/devices/*; do
        [ "$(cat "$_d/idVendor" 2>/dev/null)" = 1c7a ] || continue
        case "$(cat "$_d/idProduct" 2>/dev/null)" in 05a5|05a1) return 0 ;; esac
    done
    echo "that reader was not found on this computer"
    return 1
}
if [ "$1" -eq 1 ]; then
    if [ "${FPRINT_SDCP_FORCE:-0}" != 1 ] && ! _why=$(fix_hardware_problem); then
        cat >&2 <<EOF

fingerprint-fix-sdcp is only for the Samsung Galaxy Book4 and Book5 (64-bit
Intel/AMD) with the Egis fingerprint reader (USB 1c7a:05a5 or 1c7a:05a1),
but $_why.
Nothing was installed: any other fingerprint reader works with your distro's
own driver. To install anyway (e.g. building a system image for a Galaxy Book):
  sudo FPRINT_SDCP_FORCE=1 dnf install ./fingerprint-fix-sdcp-*.rpm ./galaxybook-fingerprint-manager-*.rpm

EOF
        exit 1
    fi
fi
# First install over a copy made by install.sh: remove that copy with its own
# cleanups (driver, then Manager; enrolled fingerprints are kept), or its
# drop-in in /etc would override this package's. Before 2.0.0 one cleanup
# removed everything.
if [ "$1" -eq 1 ]; then
    # The cleanups delete the libfprint hash that marks an earlier install:
    # note it, so the Manager's %post leaves fingerprint login as it was.
    if [ -x /usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh ] \
            || [ -x /usr/local/bin/galaxybook-fingerprint-manager-cleanup.sh ]; then
        mkdir -p /var/lib/samsung-galaxybook
        touch /var/lib/samsung-galaxybook/keep-pam-setting
    fi
    for c in /usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh \
             /usr/local/bin/galaxybook-fingerprint-manager-cleanup.sh; do
        if [ -x "$c" ]; then
            echo "Removing the copy of fingerprint-fix-sdcp installed with install.sh (fingerprints are kept)"
            "$c" || :
        fi
    done
    [ -f /usr/local/share/icons/hicolor/icon-theme.cache ] && command -v gtk-update-icon-cache >/dev/null 2>&1 \
        && gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || :
fi

%post
# The hourly release check: enabled for every user once (first install, or
# the upgrade that brings it); after that the admin's choice is kept.
if [ ! -e /var/lib/samsung-galaxybook/fingerprint-fix-sdcp-update-check.timer.set-up ]; then
    systemctl --global enable fingerprint-fix-sdcp-update-check.timer >/dev/null 2>&1 || :
    mkdir -p /var/lib/samsung-galaxybook && touch /var/lib/samsung-galaxybook/fingerprint-fix-sdcp-update-check.timer.set-up
fi
# Another fingerprint fix's fprintd setup (e.g. a manual install of Abdallah's
# libfprint-egismoc-sdcp): moved aside, with a backup and how to restore it.
%{scriptdir}/other-fix.sh takeover || :
# fprintd picks up the drop-in now; the drop-in changes its environment, so
# reload first (systemd's own reload runs at the end of the transaction).
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart fprintd.service >/dev/null 2>&1 || :
# Fingerprint login on, once per computer (whichever package comes first).
bash %{pkglibdir}/pam/pam-first-install.sh || :

%preun
%systemd_user_preun %{fix_update}
if [ "$1" -eq 0 ]; then
    rm -f /var/lib/samsung-galaxybook/fingerprint-fix-sdcp-update-check.timer.set-up
fi

%postun
# Removed (not upgraded): fprintd goes back to the distro's libfprint; the
# Manager, fingerprint login and enrolled fingerprints stay.
if [ "$1" -eq 0 ]; then
    rm -f /run/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf \
          /run/samsung-galaxybook/fprintd-sdcp.env
fi
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart fprintd.service >/dev/null 2>&1 || :

%post -n %{mgrname}
%systemd_post %{boot_check}
%systemd_user_post %{user_check}
# The hourly release check: enabled for every user once (first install, or
# the upgrade that brings it); after that the admin's choice is kept.
if [ ! -e /var/lib/samsung-galaxybook/galaxybook-fingerprint-manager-update-check.timer.set-up ]; then
    systemctl --global enable galaxybook-fingerprint-manager-update-check.timer >/dev/null 2>&1 || :
    mkdir -p /var/lib/samsung-galaxybook && touch /var/lib/samsung-galaxybook/galaxybook-fingerprint-manager-update-check.timer.set-up
fi
# Fingerprint login on, once per computer (whichever package comes first;
# before the libfprint hash below, which marks computers set up by 2.1 and
# earlier). FPRINT_PAM=0 leaves it off.
bash %{mgrdir}/tools/pam-first-install.sh || :
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
    echo "Open 'Galaxy Book Fingerprint Manager' from the app menu to enrol a finger."
    # The same hint as a notification now, for anyone logged into a desktop
    # (each hint is shown once per user, so an upgrade from 1.x shows nothing new).
    %{mgrscriptdir}/notify-users.sh || :
fi

%preun -n %{mgrname}
%systemd_preun %{boot_check}
%systemd_user_preun %{user_check} %{mgr_update}
if [ "$1" -eq 0 ]; then
    %{mgrscriptdir}/checks-off-hint.sh || :
    rm -f /var/lib/samsung-galaxybook/galaxybook-fingerprint-manager-update-check.timer.set-up
fi

%postun -n %{mgrname}
systemctl daemon-reload >/dev/null 2>&1 || :

%files
%license LICENSE
%{pkglibdir}/
%{scriptdir}/
%dir %{_unitdir}/fprintd.service.d
%{_userunitdir}/fingerprint-fix-sdcp-update-check.service
%{_userunitdir}/%{fix_update}
%{_userpresetdir}/80-%{name}.preset
%{_unitdir}/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf

%files -n %{mgrname}
%license LICENSE
%doc README.md CHANGELOG.md
%{mgrdir}/
%{mgrscriptdir}/
%{_unitdir}/samsung-galaxybook-fprint-sdcp-monitor.service
%{_unitdir}/%{boot_check}
%{_userunitdir}/samsung-galaxybook-fprint-sdcp-user-check.service
%{_userunitdir}/%{user_check}
%{_userunitdir}/galaxybook-fingerprint-manager-update-check.service
%{_userunitdir}/%{mgr_update}
%{_userunitdir}/samsung-galaxybook-session.target
%{_presetdir}/80-%{mgrname}.preset
%{_userpresetdir}/80-%{mgrname}.preset
%config(noreplace) %{_sysconfdir}/xdg/autostart/fingerprint-fix-sdcp-session.desktop
%{_datadir}/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules
%{_datadir}/polkit-1/actions/io.github.david-bartlett.galaxybook-fingerprint-manager.policy
%{_datadir}/applications/io.github.david_bartlett.GalaxyBookFingerprintManager.desktop
%{_datadir}/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg
%{_bindir}/galaxybook-fingerprint-manager
