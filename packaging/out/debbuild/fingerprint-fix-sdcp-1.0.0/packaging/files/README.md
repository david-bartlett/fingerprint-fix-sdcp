# Installed scripts and units

The scripts, systemd units, polkit files and menu entries the fix installs. Paths inside them are written as `@FPRINT_LIB_DIR@`, `@MGR_BIN@` and so on, and filled in by `packaging/render.sh` from `lib/fixpaths.sh`:

```bash
bash packaging/render.sh local monitor.sh.in      # as install.sh installs it (/usr/local, /etc)
bash packaging/render.sh package monitor.sh.in    # as the packages install it (/usr)
```

`install.sh` and the packages both render these files, so a change here reaches both. `cleanup.sh.in` is `install.sh` only: a package is removed by its package manager.
