#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Fingerprint Manager
# =============================================================================
# A small window for the fingerprints on this laptop's sensor:
#   • which fingers are enrolled on this install, and whether each one is
#     still stored on the sensor (or was wiped, e.g. by Windows)
#   • every template on the sensor, and which of them this install uses
#   • test a fingerprint, remove dead records, delete templates, wipe the sensor
#   • export / import fingerprints to share them with another install
#
#   python3 fingerprint-manager.py          (run as yourself, not with sudo)
#
# It asks for your password once (pkexec) to start fingerprint-manager-helper.py,
# which does the root work. Needs fingerprint-fix-sdcp installed, PyGObject
# with GTK 3, and libfprint's GObject introspection data.
# =============================================================================
import os
import shutil
import subprocess
import sys
import threading
import json

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib, Pango
except (ImportError, ValueError) as e:
    sys.exit(f"Fingerprint Manager needs PyGObject with GTK 3 ({e}).\n"
             "  Fedora:  sudo dnf install python3-gobject gtk3\n"
             "  Debian / Ubuntu / Mint / MX:  sudo apt install python3-gi gir1.2-gtk-3.0\n"
             "  Arch / CachyOS:  sudo pacman -S python-gobject gtk3")

HERE = os.path.dirname(os.path.realpath(__file__))
HELPER = os.path.join(HERE, "fingerprint-manager-helper.py")
TITLE = "Fingerprint Manager"
EXPORT_NAME = "fingerprint-export.tgz"


# ── The root helper, started once ─────────────────────────────────────────────
class Helper:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        py = sys.executable or shutil.which("python3")
        if os.geteuid() == 0:
            cmd = [py, HELPER]
        else:
            if not shutil.which("pkexec"):
                raise RuntimeError("pkexec is not installed (it comes with polkit).")
            cmd = ["pkexec", py, HELPER]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)
        line = self.proc.stdout.readline()
        if not line:
            err = (self.proc.stderr.read() or "").strip()
            rc = self.proc.wait()
            self.proc = None
            if rc in (126, 127):
                raise RuntimeError("Authentication was cancelled or refused.\n"
                                   "Press Refresh to try again.")
            raise RuntimeError(err or f"The helper did not start (exit code {rc}).")

    def call(self, action, **kw):
        with self.lock:
            self.start()
            self.proc.stdin.write(json.dumps(dict(kw, action=action)) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                err = (self.proc.stderr.read() or "").strip()
                self.proc = None
                raise RuntimeError(err or "The helper stopped unexpectedly.")
            reply = json.loads(line)
            if not reply.get("ok"):
                raise RuntimeError(reply.get("error") or "Unknown error")
            return reply["result"]

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
            except Exception:
                pass


# ── Window ────────────────────────────────────────────────────────────────────
class Manager(Gtk.Window):
    def __init__(self):
        super().__init__(title=TITLE)
        self.set_default_size(720, 620)
        self.set_icon_name("fingerprint-gui")
        self.helper = Helper()
        self.status = None
        self.busy = False

        hb = Gtk.HeaderBar(show_close_button=True, title=TITLE)
        self.set_titlebar(hb)
        self.refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.refresh_btn.set_tooltip_text("Read the sensor again")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh())
        hb.pack_start(self.refresh_btn)
        self.spinner = Gtk.Spinner()
        hb.pack_end(self.spinner)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.add(box)

        self.info = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.info.get_style_context().add_class("dim-label")
        box.pack_start(self.info, False, False, 0)

        self.msg_bar = Gtk.InfoBar(show_close_button=True)
        self.msg_bar.connect("response", lambda b, *_: b.hide())
        self.msg_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.msg_bar.get_content_area().add(self.msg_label)
        self.msg_bar.set_no_show_all(True)
        self.msg_label.show()
        box.pack_start(self.msg_bar, False, False, 0)

        # Records on this install: user, finger, enrolled, status, finger no., on sensor
        self.rec_store = Gtk.ListStore(str, str, str, str, str, int)
        self.rec_view = self._table(self.rec_store, ["User", "Finger", "Enrolled", "Status"])
        box.pack_start(self._section("Fingerprints on this install", self.rec_view,
            "Each record here points at a template on the sensor. If that template is gone "
            "(re-enrolled elsewhere, or removed by Windows) the record is dead and can never match."),
            True, True, 0)
        row = Gtk.Box(spacing=6)
        self.test_btn = self._button(row, "Test fingerprint", self.on_test,
                                     "Run fprintd-verify and touch the sensor")
        self.dead_btn = self._button(row, "Remove dead records", self.on_remove_dead,
                                     "Clear records whose template is no longer on the sensor")
        self.unlink_btn = self._button(row, "Remove from this install…", self.on_remove_selected,
                                       "Remove the selected records here only — the sensor "
                                       "keeps the template, so installs sharing it keep working")
        box.pack_start(row, False, False, 0)

        # Templates on the sensor: id, used by, used here (1/0)
        self.tpl_store = Gtk.ListStore(str, str, int)
        self.tpl_view = self._table(self.tpl_store, ["Template", "Used by"])
        box.pack_start(self._section("Templates on the sensor", self.tpl_view,
            "Templates not used here may belong to another Linux install, another user, "
            "or Windows Hello. This install can't tell which."), True, True, 0)
        row = Gtk.Box(spacing=6)
        self.del_btn = self._button(row, "Delete from sensor…", self.on_delete_templates,
                                    "Delete the selected templates from the sensor")
        box.pack_start(row, False, False, 0)

        box.pack_start(Gtk.Separator(), False, False, 0)
        row = Gtk.Box(spacing=6)
        self.export_btn = self._button(row, "Export…", self.on_export,
                                       "Save your fingerprints to share with another install")
        self.import_btn = self._button(row, "Import…", self.on_import,
                                       "Load fingerprints exported on another install")
        self.wipe_btn = Gtk.Button(label="Wipe sensor…")
        self.wipe_btn.get_style_context().add_class("destructive-action")
        self.wipe_btn.set_tooltip_text("Delete every template on the sensor — every install and Windows")
        self.wipe_btn.connect("clicked", self.on_wipe)
        row.pack_end(self.wipe_btn, False, False, 0)
        box.pack_start(row, False, False, 0)

        self.rec_view.get_selection().connect("changed", lambda *_: self._update_buttons())
        self.tpl_view.get_selection().connect("changed", lambda *_: self._update_buttons())
        self.connect("destroy", self.on_quit)
        self.show_all()
        self._update_buttons()
        GLib.idle_add(self.refresh)

    # ── building blocks ──
    def _table(self, store, titles):
        view = Gtk.TreeView(model=store)
        view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        for i, t in enumerate(titles):
            last = i == len(titles) - 1
            cell = Gtk.CellRendererText(
                ellipsize=Pango.EllipsizeMode.END if last else Pango.EllipsizeMode.NONE)
            col = Gtk.TreeViewColumn(t, cell, text=i)
            col.set_resizable(True)
            col.set_expand(last)
            view.append_column(col)
        return view

    def _section(self, title, view, hint):
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        vb.pack_start(lbl, False, False, 0)
        h = Gtk.Label(label=hint, xalign=0, wrap=True)
        h.get_style_context().add_class("dim-label")
        vb.pack_start(h, False, False, 0)
        sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        sw.set_min_content_height(110)
        sw.add(view)
        vb.pack_start(sw, True, True, 0)
        return vb

    def _button(self, row, label, cb, tip):
        b = Gtk.Button(label=label)
        b.set_tooltip_text(tip)
        b.connect("clicked", cb)
        row.pack_start(b, False, False, 0)
        return b

    def _selected(self, view, col):
        model, paths = view.get_selection().get_selected_rows()
        return [model[p] for p in paths]

    def _update_buttons(self):
        st = self.status
        ready = st is not None and not self.busy
        recs = st["records"] if st else []
        mine = [r for r in recs if r["user"] == (st or {}).get("user")]
        self.refresh_btn.set_sensitive(not self.busy)
        self.test_btn.set_sensitive(ready and any(r["on_sensor"] for r in mine))
        self.dead_btn.set_sensitive(ready and any(r["on_sensor"] is False for r in recs))
        self.unlink_btn.set_sensitive(ready and bool(self._selected(self.rec_view, 0)))
        self.del_btn.set_sensitive(ready and st["features"].get("STORAGE_DELETE", False)
                                   and bool(self._selected(self.tpl_view, 0)) if ready else False)
        self.export_btn.set_sensitive(ready and any(r["on_sensor"] for r in mine))
        self.import_btn.set_sensitive(ready)
        self.wipe_btn.set_sensitive(ready and bool(st["templates"] or recs))

    # ── messages ──
    def message(self, text, kind=Gtk.MessageType.INFO):
        self.msg_bar.set_message_type(kind)
        self.msg_label.set_text(text)
        self.msg_bar.show()

    def confirm(self, title, text, ok_label, destructive=True):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE, text=title)
        d.format_secondary_text(text)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = d.add_button(ok_label, Gtk.ResponseType.OK)
        if destructive:
            ok.get_style_context().add_class("destructive-action")
        d.set_default_response(Gtk.ResponseType.CANCEL)
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.OK

    def show_output(self, title, text, kind=Gtk.MessageType.INFO):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=kind,
                              buttons=Gtk.ButtonsType.CLOSE, text=title)
        d.format_secondary_text(text)
        d.run()
        d.destroy()

    # ── running helper jobs off the GUI thread ──
    def run_job(self, action, done=None, **kw):
        self.busy = True
        self.spinner.start()
        self._update_buttons()

        def work():
            try:
                res, err = self.helper.call(action, **kw), None
            except Exception as e:
                res, err = None, str(e)
            GLib.idle_add(finish, res, err)

        def finish(res, err):
            self.busy = False
            self.spinner.stop()
            self._update_buttons()
            if done:
                done(res, err)
            return False

        threading.Thread(target=work, daemon=True).start()

    def refresh(self, after=None):
        self.msg_bar.hide()

        def done(st, err):
            if err:
                self.status = None
                self.rec_store.clear()
                self.tpl_store.clear()
                self.info.set_text("")
                self.message(err, Gtk.MessageType.ERROR)
            else:
                self.show_status(st)
            self._update_buttons()
            if after:
                after()

        self.info.set_text("Reading the sensor…")
        self.run_job("status", done)
        return False

    def show_status(self, st):
        self.status = st
        self.rec_store.clear()
        for r in st["records"]:
            if r.get("error"):
                state = f"Unreadable record ({r['error']})"
            elif r["on_sensor"]:
                state = "✓ On the sensor"
            else:
                state = "✗ Gone from the sensor — dead record"
            self.rec_store.append([r["user"], r["name"], r["enrolled"], state, r["finger"],
                                   1 if r["on_sensor"] else 0])
        self.tpl_store.clear()
        for t in st["templates"]:
            used = ", ".join(t["used_by"]) if t["used_by"] else \
                "Not used here — another install, another user, or Windows Hello?"
            self.tpl_store.append([t["id"], used, 1 if t["used_by"] else 0])
        marker = st.get("marker") or "unknown"
        self.info.set_text(f"{st.get('device_name', 'Fingerprint sensor')}  ·  {st['usb_id']}  ·  "
                           f"sensor {st['serial']}\nfingerprint-fix-sdcp: {marker}\n"
                           f"{len(st['records'])} record(s) on this install  ·  "
                           f"{len(st['templates'])} template(s) on the sensor")
        dead = [r for r in st["records"] if r["on_sensor"] is False]
        if dead:
            names = ", ".join(f"{r['name']} ({r['user']})" for r in dead)
            self.message(f"These fingerprints are no longer on the sensor: {names}.\n"
                         "Remove the dead records, then import a current export or enrol again.",
                         Gtk.MessageType.WARNING)

    def after_job(self, title):
        def done(res, err):
            if err:
                self.refresh(lambda: self.message(err, Gtk.MessageType.ERROR))
                return
            lines = []
            if res.get("output"):
                lines.append(res["output"])
            if res.get("deleted") not in (None, [], 0):
                n = res["deleted"] if isinstance(res["deleted"], int) else len(res["deleted"])
                lines.append(f"Deleted {n} template(s) from the sensor.")
            if res.get("left"):
                lines.append(f"{res['left']} template(s) could not be deleted.")
            if res.get("moved"):
                head, sep, tail = res["moved"][0].partition("/removed-fingerprints/")
                folder = f"{head}{sep}{tail.split('/')[0]}/" if sep \
                    else os.path.dirname(res["moved"][0]) + "/"
                lines.append(f"Moved {len(res['moved'])} record(s) to {folder}")
            self.refresh(lambda: self.message(f"{title}: " + ("\n".join(lines) or "done."),
                                              Gtk.MessageType.INFO))
        return done

    # ── actions ──
    def on_test(self, _btn):
        if not shutil.which("fprintd-verify"):
            return self.message("fprintd-verify is not installed.", Gtk.MessageType.ERROR)
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.CANCEL, text="Touch the fingerprint sensor")
        d.format_secondary_text("Using any finger enrolled for you on this install…")
        proc = subprocess.Popen(["fprintd-verify"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)

        def wait():
            try:
                out, _ = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()
            GLib.idle_add(finished, out)

        def finished(out):
            if not closed[0]:
                d.response(Gtk.ResponseType.NONE)
            result = next((l for l in out.splitlines() if "Verify result" in l), "")
            if "verify-match" in result:
                self.message("✓ Fingerprint matched.", Gtk.MessageType.INFO)
            elif proc.returncode is not None and proc.returncode < 0:
                pass  # cancelled
            else:
                self.message("✗ No match.\n" + (out.strip().splitlines()[-1] if out.strip() else ""),
                             Gtk.MessageType.WARNING)
            return False

        closed = [False]
        threading.Thread(target=wait, daemon=True).start()
        if d.run() == Gtk.ResponseType.CANCEL and proc.poll() is None:
            proc.terminate()
        closed[0] = True
        d.destroy()

    def on_remove_dead(self, _btn):
        dead = [r for r in self.status["records"] if r["on_sensor"] is False]
        names = "\n".join(f"  • {r['name']} ({r['user']})" for r in dead)
        if self.confirm("Remove dead records?",
                        f"Their templates are no longer on the sensor, so they can never match:\n"
                        f"{names}\n\nThe records are moved to "
                        "/var/lib/samsung-galaxybook/removed-fingerprints/. "
                        "Nothing on the sensor changes.", "Remove", destructive=False):
            self.run_job("remove_records", self.after_job("Removed dead records"),
                         records=[{"user": r["user"], "finger": r["finger"]} for r in dead])

    def on_remove_selected(self, _btn):
        rows = self._selected(self.rec_view, 0)
        names = "\n".join(f"  • {r[1]} ({r[0]})" for r in rows)
        if self.confirm("Remove from this install only?",
                        f"{names}\n\nThese fingerprints stop working on this install. Their templates "
                        "stay on the sensor, so other installs sharing them keep working. The records "
                        "are moved to /var/lib/samsung-galaxybook/removed-fingerprints/.",
                        "Remove"):
            self.run_job("remove_records", self.after_job("Removed from this install"),
                         records=[{"user": r[0], "finger": r[4]} for r in rows])

    def on_delete_templates(self, _btn):
        rows = self._selected(self.tpl_view, 0)
        used = [r for r in rows if r[2]]
        unused = [r for r in rows if not r[2]]
        text = []
        if used:
            text.append("Used by this install: " + "; ".join(r[1] for r in used) + ".\n"
                        "They stop working here and on every other install sharing them. "
                        "Their records here are moved aside.")
        if unused:
            text.append(f"{len(unused)} template(s) not used by this install. They may belong to "
                        "another Linux install, another user, or Windows Hello — fingerprint "
                        "login stops working there until you enrol again.")
        if self.confirm(f"Delete {len(rows)} template(s) from the sensor?",
                        "\n\n".join(text) + "\n\nThis can't be undone.", "Delete"):
            self.run_job("delete_templates", self.after_job("Deleted from the sensor"),
                         ids=[r[0] for r in rows])

    def on_wipe(self, _btn):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE, text="Wipe the whole sensor?")
        d.format_secondary_text(
            "This deletes EVERY template on the sensor — the fingerprints of every Linux install "
            "and of Windows Hello. Every record on this install is moved aside. Everyone has to "
            "enrol again, and exports made before this stop working.\n\nType WIPE to confirm.")
        entry = Gtk.Entry(activates_default=True)
        d.get_message_area().pack_start(entry, False, False, 0)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = d.add_button("Wipe", Gtk.ResponseType.OK)
        ok.get_style_context().add_class("destructive-action")
        ok.set_sensitive(False)
        entry.connect("changed", lambda e: ok.set_sensitive(e.get_text().strip().upper() == "WIPE"))
        d.show_all()
        r = d.run()
        confirmed = r == Gtk.ResponseType.OK and entry.get_text().strip().upper() == "WIPE"
        d.destroy()
        if confirmed:
            self.run_job("wipe", self.after_job("Sensor wiped"))

    def _chooser(self, title, action, ok_label):
        d = Gtk.FileChooserDialog(title=title, transient_for=self, action=action)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        d.add_button(ok_label, Gtk.ResponseType.OK)
        f = Gtk.FileFilter()
        f.set_name("Fingerprint exports (*.tgz)")
        f.add_pattern("*.tgz")
        f.add_pattern("*.tar.gz")
        d.add_filter(f)
        d.set_current_folder(os.path.expanduser("~"))
        return d

    def on_export(self, _btn):
        d = self._chooser("Export fingerprints", Gtk.FileChooserAction.SAVE, "Export")
        d.set_current_name(EXPORT_NAME)
        d.set_do_overwrite_confirmation(True)
        path = d.get_filename() if d.run() == Gtk.ResponseType.OK else None
        d.destroy()
        if path:
            if not path.endswith((".tgz", ".tar.gz")):
                path += ".tgz"
            self.run_job("export", self.after_job("Exported"), file=path)

    def on_import(self, _btn):
        d = self._chooser("Import fingerprints", Gtk.FileChooserAction.OPEN, "Import")
        default = os.path.expanduser(f"~/{EXPORT_NAME}")
        if os.path.isfile(default):
            d.set_filename(default)
        path = d.get_filename() if d.run() == Gtk.ResponseType.OK else None
        d.destroy()
        if not path:
            return
        mine = [r for r in self.status["records"] if r["user"] == self.status["user"]]
        replace = False
        if mine:
            names = ", ".join(r["name"] for r in mine)
            if not self.confirm("Replace your fingerprints on this install?",
                                f"You already have {names} here. Importing replaces them with the "
                                "ones in this file, once the file has been checked against the "
                                "sensor. The old records are moved to "
                                "/var/lib/samsung-galaxybook/replaced-fingerprints/ — nothing is "
                                "deleted from the sensor.", "Replace"):
                return
            replace = True
        self.run_job("import", self.after_job("Imported"), file=path, replace=replace)

    def on_quit(self, *_):
        self.helper.stop()
        Gtk.main_quit()


def main():
    if os.geteuid() == 0 and not os.environ.get("SUDO_UID"):
        sys.exit("Run Fingerprint Manager as yourself (it asks for your password when needed).")
    if not os.path.isfile(HELPER):
        sys.exit(f"Missing {HELPER} — keep both files in the same folder.")
    Manager()
    Gtk.main()


if __name__ == "__main__":
    main()
