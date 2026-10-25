#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book Fixes — Galaxy Book Fingerprint Manager (fingerprint-fix-sdcp)
# =============================================================================
# A small window for the fingerprints on this laptop's sensor:
#   • which fingers are enrolled on this install, and whether each one is
#     still stored on the sensor (or was wiped, e.g. by Windows)
#   • every template on the sensor, and which of them this install uses
#   • test a fingerprint, remove dead records, delete templates, wipe the sensor
#   • export / import fingerprints to share them with another install
#
#   galaxybook-fingerprint-manager   (installed by install.sh; also in the app
#                                     menu as "Galaxy Book Fingerprint Manager")
#   ./fingerprint-manager.sh         (from the fix folder, e.g. while developing)
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

# The app ID: on Wayland the panel/taskbar takes the window's icon from the
# .desktop file with this name (install.sh installs it), and ignores icons set
# on the window itself. It must be set before GTK starts, i.e. before Gtk is
# imported. It is also the icon's name.
APP_ID = "galaxybook-fingerprint-manager"

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib
    GLib.set_prgname(APP_ID)
    GLib.set_application_name("Galaxy Book Fingerprint Manager")
    from gi.repository import Gtk, Pango
except (ImportError, ValueError) as e:
    sys.exit(f"Fingerprint Manager needs PyGObject with GTK 3 ({e}).\n"
             "  Fedora:  sudo dnf install python3-gobject gtk3\n"
             "  Debian / Ubuntu / Mint / MX:  sudo apt install python3-gi gir1.2-gtk-3.0\n"
             "  Arch / CachyOS:  sudo pacman -S python-gobject gtk3")

HERE = os.path.dirname(os.path.realpath(__file__))
HELPER = os.path.join(HERE, "fingerprint-manager-helper.py")
TITLE = "Galaxy Book Fingerprint Manager"
EXPORT_NAME = "fingerprint-export.tgz"
FINGERS = ["right-index-finger", "right-middle-finger", "right-thumb", "right-ring-finger",
           "right-little-finger", "left-index-finger", "left-middle-finger", "left-thumb",
           "left-ring-finger", "left-little-finger"]
GREEN, RED, AMBER = "#26a269", "#c01c28", "#e5a50a"


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
            # Run the helper itself (not "python3 helper"), so polkit can show
            # this app's own message: install.sh installs a policy for the
            # installed helper's path.
            cmd = ["pkexec", HELPER] if os.access(HELPER, os.X_OK) else ["pkexec", py, HELPER]
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

    def cancel(self):
        """Stop a running fingerprint test (no reply; the test call returns)."""
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write(json.dumps({"action": "cancel"}) + "\n")
                self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
            except Exception:
                pass


# ── Window ────────────────────────────────────────────────────────────────────
CSS = b"""
.fpm-card { border: 1px solid alpha(currentColor, 0.15); border-radius: 8px; padding: 10px 12px; }
.fpm-hint { font-size: 90%; }
.fpm-status { font-size: 90%; }
.fpm-fcard { background-color: @theme_base_color; border: 1px solid alpha(@theme_fg_color, 0.15);
             border-radius: 10px; padding: 10px 6px 9px 6px; }
.fpm-add { background-color: transparent; border: 1px dashed @theme_selected_bg_color; }
.fpm-add label { color: @theme_selected_bg_color; }
.fpm-plus { font-size: 26px; }
.fpm-lcard { background-color: @theme_base_color; border: 1px solid alpha(@theme_fg_color, 0.15);
             border-radius: 8px; padding: 6px 10px; }
.fpm-name { font-weight: bold; }
.fpm-small { font-size: 85%; }
.fpm-pill { border-radius: 9px; padding: 1px 8px; font-size: 85%; font-weight: bold; }
.fpm-ok { background-color: alpha(#26a269, 0.18); color: #26a269; }
.fpm-dead { background-color: alpha(#e01b24, 0.16); color: #e01b24; }
.fpm-unknown { background-color: alpha(@theme_fg_color, 0.10); }
flowbox.fpm-cards, list.fpm-list { background-color: transparent; }
flowbox.fpm-cards flowboxchild { padding: 3px; background-color: transparent; }
flowbox.fpm-cards flowboxchild:selected { background-color: transparent; }
flowbox.fpm-cards flowboxchild:selected .fpm-fcard { border: 2px solid @theme_selected_bg_color; padding: 9px 5px 8px 5px; }
list.fpm-list row { padding: 0; margin-bottom: 6px; background-color: transparent; }
list.fpm-list row:selected { background-color: transparent; }
list.fpm-list row:selected .fpm-lcard { border-color: @theme_selected_bg_color;
                                        background-color: alpha(@theme_selected_bg_color, 0.10); }
flowbox.fpm-cards flowboxchild:selected label, list.fpm-list row:selected label { color: @theme_fg_color; }
flowbox.fpm-cards flowboxchild:selected label.fpm-ok, list.fpm-list row:selected label.fpm-ok { color: #26a269; }
flowbox.fpm-cards flowboxchild:selected label.fpm-dead, list.fpm-list row:selected label.fpm-dead { color: #e01b24; }
flowbox.fpm-cards flowboxchild:selected .fpm-add label { color: @theme_selected_bg_color; }
.fpm-free { background-color: transparent; border: 1px dashed alpha(@theme_fg_color, 0.30); }
.fpm-free label { color: alpha(@theme_fg_color, 0.45); }
.fpm-id { font-family: monospace; font-size: 80%; }
.fpm-slots { font-weight: bold; }
"""

# The egismoc sensor stores up to this many templates (EGISMOC_MAX_ENROLL_NUM).
SENSOR_SLOTS = 10

# ── fingerprint pictures, names and the remembered view ─────────────────────
SETTINGS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                        APP_ID, "settings")


def load_view():
    try:
        with open(SETTINGS) as f:
            return "list" if "view=list" in f.read() else "icons"
    except OSError:
        return "icons"


def save_view(view):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w") as f:
            f.write(f"view={view}\n")
    except OSError:
        pass


# The fingerprint drawing (64×64 units): start point, then cubic segments.
FP_PATHS = [
    ((14, 22), [(19, 12, 32, 8, 42, 12), (47, 14, 51, 18, 53, 23)]),
    ((12, 33), [(12, 23, 21, 17, 31, 17), (42, 17, 50, 24, 50, 33), (50, 37, 49.5, 40, 48.5, 43)]),
    ((18, 47), [(16, 42, 17, 35, 19, 31), (22, 25, 28, 23, 33, 24.5), (38, 26, 41, 30, 41, 35),
                (41, 40, 40, 45, 38, 49)]),
    ((24, 50), [(22, 45, 22, 39, 24, 34), (25.5, 30.5, 28.5, 29, 31.5, 30), (34.5, 31, 35.5, 34, 35.5, 37),
                (35.5, 42, 34, 47, 32, 51)]),
    ((30, 36), [(30.5, 42, 29.5, 47, 27, 52)]),
]
FP_COLOURS = {"ok": (0.149, 0.635, 0.412), "dead": (0.878, 0.106, 0.141),
              "unknown": (0.60, 0.60, 0.59), "add": (0.208, 0.518, 0.894)}


try:                                  # drawing needs PyGObject's cairo support
    gi.require_foreign("cairo")
    HAVE_CAIRO = True
except Exception:                     # (python3-gi-cairo on Debian/Ubuntu)
    HAVE_CAIRO = False


class FingerprintIcon(Gtk.DrawingArea):
    def __init__(self, kind, size):
        super().__init__()
        self.kind = kind
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.CENTER)
        if HAVE_CAIRO:
            self.connect("draw", self._draw)

    def _draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        sc = min(w, h) / 46.0                       # the drawing spans about 46 units
        cr.translate(w / 2 - 32.5 * sc, h / 2 - 30 * sc)
        cr.scale(sc, sc)
        cr.set_source_rgb(*FP_COLOURS.get(self.kind, FP_COLOURS["unknown"]))
        cr.set_line_width(3.2)
        cr.set_line_cap(1)                          # round
        for (x, y), segs in FP_PATHS:
            cr.move_to(x, y)
            for seg in segs:
                cr.curve_to(*seg)
            cr.stroke()
        return False


def short_finger(name):
    """right-index-finger -> Right index; left-thumb -> Left thumb"""
    parts = name.split("-")
    if len(parts) >= 2 and parts[0] in ("left", "right"):
        return f"{parts[0].capitalize()} {parts[1]}"
    return name


def long_finger(name):
    """right-index-finger -> Right index finger"""
    return name.replace("-", " ").capitalize()


def nice_date(d, year=False):
    try:
        import datetime
        return datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%-d %b %Y" if year else "%-d %b")
    except (ValueError, TypeError):
        return d or ""


def rec_kind(r):
    if r.get("error"):
        return "unknown", "Unreadable"
    return ("ok", "On the sensor") if r["on_sensor"] else ("dead", "Gone from sensor")


def summarise(text):
    """One line from a script's output: its last [INFO]/[ERROR] line, or the
    last line. The full text is kept for the Details button."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    tagged = [l for l in lines if l.startswith(("[INFO]", "[ERROR]", "[WARN]"))]
    pick = (tagged or lines or [""])[-1]
    for tag in ("[INFO]", "[ERROR]", "[WARN]"):
        pick = pick.replace(tag, "").strip()
    return pick


class Manager(Gtk.Window):
    def __init__(self):
        super().__init__(title=TITLE)
        self.set_default_size(560, 600)
        self.set_icon_name(APP_ID)
        self.helper = Helper()
        self.status = None
        self.busy = False
        self._pam_syncing = False
        self._msg_timer = 0
        self._msg_details = None

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # ── header bar: refresh · [Fingerprints | Sensor] · menu ──
        hb = Gtk.HeaderBar(show_close_button=True)
        self.set_titlebar(hb)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        hb.set_custom_title(switcher)
        self.refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.refresh_btn.set_tooltip_text("Read the sensor again")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh())
        hb.pack_start(self.refresh_btn)
        self.spinner = Gtk.Spinner()
        hb.pack_start(self.spinner)

        menu = Gtk.Menu()
        self.export_item = self._menu_item(menu, "Export fingerprints…", self.on_export)
        self.import_item = self._menu_item(menu, "Import fingerprints…", self.on_import)
        menu.append(Gtk.SeparatorMenuItem())
        self.restore_item = self._menu_item(menu, "Restore removed records…", self.on_restore)
        menu.append(Gtk.SeparatorMenuItem())
        self._menu_item(menu, "About", self.on_about)
        menu.show_all()
        self.menu_btn = Gtk.MenuButton(popup=menu)
        self.menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        self.menu_btn.set_tooltip_text("Export, import, restore")
        hb.pack_end(self.menu_btn)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.add(outer)

        # ── top card: login/sudo switch + sensor line ──
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.get_style_context().add_class("fpm-card")
        row = Gtk.Box(spacing=12)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(xalign=0)
        title.set_markup("<b>Use fingerprint for login and sudo</b>")
        texts.pack_start(title, False, False, 0)
        self.pam_detail = Gtk.Label(xalign=0, wrap=True)
        self.pam_detail.get_style_context().add_class("dim-label")
        self.pam_detail.get_style_context().add_class("fpm-hint")
        texts.pack_start(self.pam_detail, False, False, 0)
        row.pack_start(texts, True, True, 0)
        self.pam_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.pam_switch.connect("state-set", self.on_pam_switch)
        row.pack_end(self.pam_switch, False, False, 0)
        card.pack_start(row, False, False, 0)
        card.pack_start(Gtk.Separator(), False, False, 0)
        self.info = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.info.get_style_context().add_class("dim-label")
        self.info.get_style_context().add_class("fpm-status")
        card.pack_start(self.info, False, False, 0)
        outer.pack_start(card, False, False, 0)

        # ── message bar: one short line, Details… for the full text ──
        self.msg_bar = Gtk.InfoBar(show_close_button=True)
        self.msg_bar.connect("response", self._on_msg_response)
        self.msg_label = Gtk.Label(xalign=0, wrap=True, lines=2,
                                   ellipsize=Pango.EllipsizeMode.END)
        msg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        msg_box.pack_start(self.msg_label, False, False, 0)
        msg_btns = Gtk.Box(spacing=6)
        self.msg_action_btn = Gtk.Button(label="")
        self.msg_action_btn.connect("clicked", lambda *_: self._on_msg_response(None, 2))
        msg_btns.pack_start(self.msg_action_btn, False, False, 0)
        self.msg_details_btn = Gtk.Button(label="Details…")
        self.msg_details_btn.connect("clicked", lambda *_: self._on_msg_response(None, 1))
        msg_btns.pack_start(self.msg_details_btn, False, False, 0)
        msg_box.pack_start(msg_btns, False, False, 0)
        self.msg_bar.get_content_area().add(msg_box)
        self.msg_bar.set_no_show_all(True)
        msg_box.show_all()
        outer.pack_start(self.msg_bar, False, False, 0)
        self._msg_action = None

        outer.pack_start(self.stack, True, True, 0)

        # ── page 1: fingerprints on this install — cards (icons) or rows (list) ──
        self.records = []                 # the status records shown, in order
        self.sel_keys = set()             # selected (user, finger) — shared by both views
        self._syncing_sel = False
        self.enrol_ok = False
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top = Gtk.Box(spacing=6)
        hint = Gtk.Label(label="Your fingers on this install. Select one to test or remove it.",
                         xalign=0, wrap=True)
        hint.get_style_context().add_class("dim-label")
        hint.get_style_context().add_class("fpm-hint")
        top.pack_start(hint, True, True, 0)
        self.view_switches = []           # (cards button, list button) per tab
        switch, self.view_icons, self.view_list = self._view_switch()
        top.pack_end(switch, False, False, 0)
        page.pack_start(top, False, False, 0)

        self.cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.MULTIPLE, homogeneous=True,
                                 min_children_per_line=2, max_children_per_line=4,
                                 column_spacing=4, row_spacing=4, valign=Gtk.Align.START,
                                 activate_on_single_click=True)
        self.cards.get_style_context().add_class("fpm-cards")
        self.cards.connect("selected-children-changed", self._on_cards_selected)
        self.rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE,
                                activate_on_single_click=False)
        self.rows.get_style_context().add_class("fpm-list")
        self.rows.connect("selected-rows-changed", self._on_rows_selected)
        self.rows.connect("row-activated", lambda _l, row: getattr(row, "is_add", False)
                          and self.on_enrol(None))
        self.rec_views = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for name, widget in (("icons", self.cards), ("list", self.rows)):
            sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            sw.set_min_content_height(200)
            sw.add(widget)
            self.rec_views.add_named(sw, name)
        page.pack_start(self.rec_views, True, True, 0)

        row = Gtk.Box(spacing=6)
        self.test_btn = self._button(row, "Test fingerprint", self.on_test,
                                     "Test the selected finger — or, with none selected, "
                                     "any of your fingers, as login and sudo do")
        self.unlink_btn = Gtk.Button(label="Remove…")
        self.unlink_btn.set_tooltip_text("Remove the selected fingerprints from this install only — "
                                         "the sensor keeps them, so installs sharing them keep working")
        self.unlink_btn.connect("clicked", self.on_remove_selected)
        row.pack_end(self.unlink_btn, False, False, 0)
        page.pack_start(row, False, False, 0)
        self.stack.add_titled(page, "fingers", "Fingerprints")

        # ── page 2: templates on the sensor — cards with free slots, or a list ──
        self.templates = []
        self.tsel = set()                 # selected template ids
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top = Gtk.Box(spacing=6)
        self.slots_label = Gtk.Label(xalign=0)
        self.slots_label.get_style_context().add_class("fpm-slots")
        top.pack_start(self.slots_label, True, True, 0)
        switch, self.tview_icons, self.tview_list = self._view_switch()
        top.pack_end(switch, False, False, 0)
        page.pack_start(top, False, False, 0)
        self.slots_bar = Gtk.ProgressBar()
        page.pack_start(self.slots_bar, False, False, 0)
        hint = Gtk.Label(label="Grey = not used by this install: another Linux install, another "
                               "user or Windows Hello. Dashed = free.", xalign=0, wrap=True)
        hint.get_style_context().add_class("dim-label")
        hint.get_style_context().add_class("fpm-hint")
        page.pack_start(hint, False, False, 0)
        self.tcards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.MULTIPLE, homogeneous=True,
                                  min_children_per_line=5, max_children_per_line=5,
                                  column_spacing=4, row_spacing=4, valign=Gtk.Align.START,
                                  activate_on_single_click=True)
        self.tcards.get_style_context().add_class("fpm-cards")
        self.tcards.connect("selected-children-changed", self._on_tcards_selected)
        self.trows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE,
                                 activate_on_single_click=False)
        self.trows.get_style_context().add_class("fpm-list")
        self.trows.connect("selected-rows-changed", self._on_trows_selected)
        self.tpl_views = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for name, widget in (("icons", self.tcards), ("list", self.trows)):
            sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            sw.set_min_content_height(200)
            sw.add(widget)
            self.tpl_views.add_named(sw, name)
        page.pack_start(self.tpl_views, True, True, 0)
        row = Gtk.Box(spacing=6)
        self.del_btn = self._button(row, "Delete…", self.on_delete_templates,
                                    "Delete the selected templates from the sensor")
        self.wipe_btn = Gtk.Button(label="Wipe sensor…")
        self.wipe_btn.get_style_context().add_class("destructive-action")
        self.wipe_btn.set_tooltip_text("Delete every template on the sensor — every install and Windows")
        self.wipe_btn.connect("clicked", self.on_wipe)
        row.pack_end(self.wipe_btn, False, False, 0)
        page.pack_start(row, False, False, 0)
        self.stack.add_titled(page, "sensor", "Sensor")
        self.pages = {"fingers": "Fingerprints", "sensor": "Sensor"}

        self._set_view(load_view(), save=False)
        self.connect("destroy", self.on_quit)
        self.show_all()
        self._set_view(load_view(), save=False)
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

    def _page(self, view, hint):
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        h = Gtk.Label(label=hint, xalign=0, wrap=True)
        h.get_style_context().add_class("dim-label")
        h.get_style_context().add_class("fpm-hint")
        vb.pack_start(h, False, False, 0)
        sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        sw.set_min_content_height(160)
        sw.add(view)
        vb.pack_start(sw, True, True, 0)
        return vb

    def _section(self, title, view, hint):            # used by dialogs
        return self._page(view, hint)

    def _button(self, row, label, cb, tip):
        b = Gtk.Button(label=label)
        b.set_tooltip_text(tip)
        b.connect("clicked", cb)
        row.pack_start(b, False, False, 0)
        return b

    def _menu_item(self, menu, label, cb):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", cb)
        menu.append(item)
        return item

    def _selected(self, view, col):
        model, paths = view.get_selection().get_selected_rows()
        return [model[p] for p in paths]

    # ── fingerprint cards / rows ──
    def _selected_recs(self):
        """Selected records as [user, short name, enrolled, state, finger no., on sensor]."""
        out = []
        for r in self.records:
            if (r["user"], r["finger"]) in self.sel_keys:
                out.append([r["user"], r["name"], r["enrolled"], rec_kind(r)[1], r["finger"],
                            1 if r["on_sensor"] else 0])
        return out

    def _view_switch(self):
        """A linked Cards | List button pair. Both tabs share the choice."""
        box = Gtk.Box()
        box.get_style_context().add_class("linked")
        icons = Gtk.RadioButton(draw_indicator=False)
        self._icon_or_text(icons, ["view-grid-symbolic", "view-app-grid-symbolic",
                                   "view-list-icons-symbolic", "view-grid"], "▦")
        icons.set_tooltip_text("Cards")
        lst = Gtk.RadioButton(group=icons, draw_indicator=False)
        self._icon_or_text(lst, ["view-list-symbolic", "view-list-details-symbolic",
                                 "view-list-details", "view-list-text"], "☰")
        lst.set_tooltip_text("List")
        box.pack_start(icons, False, False, 0)
        box.pack_start(lst, False, False, 0)
        icons.connect("toggled", lambda b: self._set_view("icons" if b.get_active() else "list"))
        self.view_switches.append((icons, lst))
        return box, icons, lst

    def _set_view(self, view, save=True):
        if getattr(self, "_setting_view", False):
            return
        self._setting_view = True
        for icons, lst in self.view_switches:
            (lst if view == "list" else icons).set_active(True)
        for stack in (getattr(self, "rec_views", None), getattr(self, "tpl_views", None)):
            if stack is not None and stack.get_child_by_name(view):
                stack.set_visible_child_name(view)
        self._setting_view = False
        if save:
            save_view(view)

    # ── sensor cards / rows ──
    def _selected_tpls(self):
        """Selected templates as [id, used-by text, used here (1/0)]."""
        return [[t["id"], ", ".join(t["used_by"]) or "Not used here", 1 if t["used_by"] else 0]
                for t in self.templates if t["id"] in self.tsel]

    def _on_tcards_selected(self, box):
        if self._syncing_sel:
            return
        ids = set()
        for child in box.get_selected_children():
            if getattr(child, "is_free", False):
                box.unselect_child(child)
            else:
                ids.add(child.tid)
        self._set_tsel(ids)

    def _on_trows_selected(self, lst):
        if self._syncing_sel:
            return
        self._set_tsel({row.tid for row in lst.get_selected_rows()})

    def _set_tsel(self, ids):
        self.tsel = ids
        self._syncing_sel = True
        for child in self.tcards.get_children():
            if getattr(child, "tid", None) in ids:
                self.tcards.select_child(child)
            else:
                self.tcards.unselect_child(child)
        for row in self.trows.get_children():
            if getattr(row, "tid", None) in ids:
                self.trows.select_row(row)
            else:
                self.trows.unselect_row(row)
        self._syncing_sel = False
        self._update_buttons()

    def _fill_templates(self, templates):
        self.templates = templates
        for w in self.tcards.get_children() + self.trows.get_children():
            w.destroy()
        used = len(templates)
        cap = max(SENSOR_SLOTS, used)
        self.slots_label.set_text(f"{used} of {cap} slots used" if templates or self.status else "")
        self.slots_bar.set_fraction(used / cap if cap else 0)
        for t in templates:
            owners = [u.split(" ", 1) for u in t["used_by"]]        # [user, finger]
            if owners:
                kind, pill = "ok", "Used here"
                title = short_finger(owners[0][1]) if len(owners[0]) > 1 else owners[0][0]
                sub = ", ".join(sorted({o[0] for o in owners}))
                long_title = long_finger(owners[0][1]) if len(owners[0]) > 1 else title
            else:
                kind, pill = "unknown", "Not used here"
                title, long_title = "Unknown", "Unknown template"
                sub = "Another install?"
            # card
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.get_style_context().add_class("fpm-fcard")
            box.pack_start(FingerprintIcon(kind, 40), False, False, 2)
            box.pack_start(self._label(title, "fpm-name", justify=Gtk.Justification.CENTER,
                                       wrap=True, max_width_chars=8), False, False, 0)
            box.pack_start(self._label(sub, "dim-label", "fpm-small", justify=Gtk.Justification.CENTER,
                                       ellipsize=Pango.EllipsizeMode.END, max_width_chars=10),
                           False, False, 0)
            box.pack_start(self._pill(kind, pill), False, False, 4)
            child = Gtk.FlowBoxChild()
            child.tid = t["id"]
            child.set_tooltip_text(f"Template {t['id']}"
                                   + (f" — used by {', '.join(t['used_by'])}" if t["used_by"]
                                      else " — not used by this install: another Linux install, "
                                           "another user, or Windows Hello"))
            child.add(box)
            self.tcards.add(child)
            # row
            hb = Gtk.Box(spacing=10)
            hb.get_style_context().add_class("fpm-lcard")
            hb.pack_start(FingerprintIcon(kind, 32), False, False, 0)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            texts.pack_start(self._label(long_title, "fpm-name", xalign=0), False, False, 0)
            detail = sub if owners else "Another Linux install, another user or Windows Hello?"
            texts.pack_start(self._label(f"{detail} · template {t['id']}", "dim-label", "fpm-small",
                                         xalign=0, ellipsize=Pango.EllipsizeMode.END), False, False, 0)
            hb.pack_start(texts, True, True, 0)
            hb.pack_start(self._pill(kind, pill), False, False, 0)
            row = Gtk.ListBoxRow()
            row.tid = t["id"]
            row.add(hb)
            self.trows.add(row)
        # free slots (cards only)
        if self.status:
            for _ in range(max(0, cap - used)):
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                for c in ("fpm-fcard", "fpm-free"):
                    box.get_style_context().add_class(c)
                box.pack_start(self._label("·", "fpm-plus", height_request=40), False, False, 2)
                box.pack_start(self._label("Free", "fpm-name"), False, False, 0)
                child = Gtk.FlowBoxChild()
                child.is_free = True
                child.set_tooltip_text("A free slot on the sensor")
                child.add(box)
                self.tcards.add(child)
        self.tcards.show_all()
        self.trows.show_all()
        self._set_tsel({i for i in self.tsel if any(t["id"] == i for t in templates)})

    def _on_cards_selected(self, box):
        if self._syncing_sel:
            return
        keys = set()
        for child in box.get_selected_children():
            if getattr(child, "is_add", False):
                box.unselect_child(child)
                if self.enrol_ok:
                    GLib.idle_add(lambda: self.on_enrol(None) and False)
                continue
            keys.add(child.key)
        self._set_selection(keys)

    def _on_rows_selected(self, lst):
        if self._syncing_sel:
            return
        self._set_selection({row.key for row in lst.get_selected_rows()
                             if not getattr(row, "is_add", False)})

    def _set_selection(self, keys):
        """Keep both views showing the same selection."""
        self.sel_keys = keys
        self._syncing_sel = True
        for child in self.cards.get_children():
            if getattr(child, "key", None) in keys:
                self.cards.select_child(child)
            else:
                self.cards.unselect_child(child)
        for row in self.rows.get_children():
            if getattr(row, "key", None) in keys:
                self.rows.select_row(row)
            else:
                self.rows.unselect_row(row)
        self._syncing_sel = False
        self._update_buttons()

    def _icon_or_text(self, button, names, text):
        """The first of these icons the theme has (themes name them differently),
        or a text symbol."""
        theme = Gtk.IconTheme.get_default()
        for n in names:
            if theme.has_icon(n):
                button.set_image(Gtk.Image.new_from_icon_name(n, Gtk.IconSize.BUTTON))
                return
        button.set_label(text)

    def _pill(self, kind, text):
        pill = Gtk.Label(label=text, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        for c in ("fpm-pill", "fpm-" + kind):
            pill.get_style_context().add_class(c)
        return pill

    def _label(self, text, *classes, **kw):
        lbl = Gtk.Label(label=text, **kw)
        for c in classes:
            lbl.get_style_context().add_class(c)
        return lbl

    def _fill_records(self, records, me):
        self.records = records
        many_users = len({r["user"] for r in records}) > 1
        self.enrol_ok = len([r for r in records if r["user"] == me]) < 10
        for w in self.cards.get_children() + self.rows.get_children():
            w.destroy()
        for r in records:
            kind, status = rec_kind(r)
            key = (r["user"], r["finger"])
            when = nice_date(r["enrolled"])
            # card
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.get_style_context().add_class("fpm-fcard")
            over = Gtk.Overlay()
            over.add(FingerprintIcon(kind, 56))
            if kind == "dead":
                warn = Gtk.Label(label="⚠", halign=Gtk.Align.END, valign=Gtk.Align.START)
                over.add_overlay(warn)
            box.pack_start(over, False, False, 2)
            box.pack_start(self._label(short_finger(r["name"]), "fpm-name",
                                       justify=Gtk.Justification.CENTER, wrap=True), False, False, 0)
            sub = (f"{r['user']} · {when}" if many_users else
                   (f"Enrolled {when}" if when else ""))
            box.pack_start(self._label(sub, "dim-label", "fpm-small"), False, False, 0)
            box.pack_start(self._pill(kind, status), False, False, 4)
            child = Gtk.FlowBoxChild()
            child.key = key
            child.set_tooltip_text(f"{long_finger(r['name'])} — {r['user']}"
                                   + (f", enrolled {nice_date(r['enrolled'], True)}" if r["enrolled"] else ""))
            child.add(box)
            self.cards.add(child)
            # row
            hb = Gtk.Box(spacing=10)
            hb.get_style_context().add_class("fpm-lcard")
            hb.pack_start(FingerprintIcon(kind, 36), False, False, 0)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            texts.pack_start(self._label(long_finger(r["name"]), "fpm-name", xalign=0), False, False, 0)
            detail = r["user"] + (f" · enrolled {nice_date(r['enrolled'], True)}" if r["enrolled"] else "")
            if kind == "dead":
                detail += " · template gone"
            texts.pack_start(self._label(detail, "dim-label", "fpm-small", xalign=0,
                                         ellipsize=Pango.EllipsizeMode.END), False, False, 0)
            hb.pack_start(texts, True, True, 0)
            hb.pack_start(self._pill(kind, status), False, False, 0)
            test = Gtk.Button(label="Test", valign=Gtk.Align.CENTER)
            test.set_sensitive(r["user"] == me and bool(r["on_sensor"]))
            test.set_tooltip_text("Test this finger")
            test.connect("clicked", lambda _b, rr=r: self.on_test(None, rec=rr))
            hb.pack_start(test, False, False, 0)
            row = Gtk.ListBoxRow()
            row.key = key
            row.add(hb)
            self.rows.add(row)
        if self.enrol_ok:
            # "Enrol a finger" card and row
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for c in ("fpm-fcard", "fpm-add"):
                box.get_style_context().add_class(c)
            box.pack_start(self._label("＋", "fpm-plus", height_request=58), False, False, 0)
            box.pack_start(self._label("Enrol a finger", "fpm-name"), False, False, 0)
            box.pack_start(self._label("Up to 10", "fpm-small"), False, False, 0)
            child = Gtk.FlowBoxChild()
            child.is_add = True
            child.set_tooltip_text("Enrol a new finger for you on this install")
            child.add(box)
            self.cards.add(child)
            hb = Gtk.Box(spacing=10)
            for c in ("fpm-lcard", "fpm-add"):
                hb.get_style_context().add_class(c)
            hb.pack_start(self._label("＋  Enrol a finger…", "fpm-name", xalign=0), True, True, 0)
            row = Gtk.ListBoxRow(selectable=False)
            row.is_add = True
            row.add(hb)
            self.rows.add(row)
        self.cards.show_all()
        self.rows.show_all()
        self._set_selection({k for k in self.sel_keys
                             if any((r["user"], r["finger"]) == k for r in records)})

    def _update_buttons(self):
        st = self.status
        ready = st is not None and not self.busy
        recs = st["records"] if st else []
        mine = [r for r in recs if r["user"] == (st or {}).get("user")]
        self.refresh_btn.set_sensitive(not self.busy)
        self.test_btn.set_sensitive(ready and any(r["on_sensor"] for r in mine))
        self.unlink_btn.set_sensitive(ready and bool(self.sel_keys))
        self.cards.set_sensitive(st is not None)
        self.rows.set_sensitive(st is not None)
        self.del_btn.set_sensitive(bool(ready and st["features"].get("STORAGE_DELETE", False)
                                        and self.tsel))
        self.wipe_btn.set_sensitive(bool(ready and (st["templates"] or recs)))
        self.export_item.set_sensitive(ready and any(r["on_sensor"] for r in mine))
        self.import_item.set_sensitive(ready)
        self.restore_item.set_sensitive(ready)
        pam = (st or {}).get("pam", {}).get("state")
        self.pam_switch.set_sensitive(ready and pam in ("enabled", "disabled", "partial"))

    # ── messages ──
    def message(self, text, kind=Gtk.MessageType.INFO, details=None, action=None):
        """Show a short message. details: full text behind a Details… button.
        action: (label, callback) for a button. Plain info messages fade after 10 s."""
        if self._msg_timer:
            GLib.source_remove(self._msg_timer)
            self._msg_timer = 0
        self.msg_bar.set_message_type(kind)
        self.msg_label.set_text(text)
        self.msg_label.set_tooltip_text(text if len(text) > 80 else None)
        self._msg_details = details if details and details.strip() != text.strip() else None
        self.msg_details_btn.set_visible(bool(self._msg_details))
        self._msg_action = action
        self.msg_action_btn.set_visible(bool(action))
        self.msg_action_btn.get_parent().set_visible(bool(action or self._msg_details))
        if action:
            self.msg_action_btn.set_label(action[0])
        self.msg_bar.show()
        if kind == Gtk.MessageType.INFO and not action:
            self._msg_timer = GLib.timeout_add_seconds(10, self._hide_message)

    def _hide_message(self):
        self._msg_timer = 0
        self.msg_bar.hide()
        return False

    def _on_msg_response(self, _bar, resp):
        if resp == 1 and self._msg_details:
            self.show_output("Details", self._msg_details)
        elif resp == 2 and self._msg_action:
            self._msg_action[1]()
        else:
            self._hide_message()

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

    def error(self, err):
        """Show a script/helper error: its key line, full text under Details…"""
        self.message(summarise(err) or err, Gtk.MessageType.ERROR, details=err)

    def refresh(self, after=None):
        if self.msg_bar.get_message_type() != Gtk.MessageType.INFO:
            self._hide_message()            # old errors/warnings; new ones follow

        def done(st, err):
            if err:
                self.status = None
                self._fill_records([], None)
                self._fill_templates([])
                self.info.set_text("")
                self.pam_detail.set_text("")
                self.error(err)
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
        self._fill_records(st["records"], st["user"])
        self._fill_templates(st["templates"])
        for name, n in (("fingers", len(st["records"])), ("sensor", len(st["templates"]))):
            self.stack.child_set_property(self.stack.get_child_by_name(name), "title",
                                          f"{self.pages[name]} ({n})")
        marker = st.get("marker") or "unknown"
        build = marker.split()[0] if marker != "unknown" else marker
        self.info.set_text(f"Sensor {st['usb_id']} · {st['serial']} · fix build {build}")
        self.info.set_tooltip_text(f"{st.get('device_name', '')}\nfingerprint-fix-sdcp: {marker}")
        self.show_pam(st.get("pam") or {})
        dead = [r for r in st["records"] if r["on_sensor"] is False]
        if dead:
            names = ", ".join(f"{r['name']} ({r['user']})" for r in dead)
            self.message(f"No longer on the sensor: {names}.", Gtk.MessageType.WARNING,
                         details="These records point at templates the sensor no longer has "
                                 "(re-enrolled elsewhere, or removed by Windows), so they can "
                                 "never match. Remove them, then import a current export or "
                                 "enrol again.",
                         action=("Remove dead records", lambda: self.on_remove_dead(None)))

    def show_pam(self, pam):
        state = pam.get("state", "unavailable")
        self._pam_syncing = True
        on = state == "enabled"
        self.pam_switch.set_active(on)
        self.pam_switch.set_state(on)
        self._pam_syncing = False
        how = " — ".join(x for x in (pam.get("method"), pam.get("detail")) if x)
        lead = {"enabled": "On", "disabled": "Off", "partial": "Partly on"}.get(state, "Not available")
        self.pam_detail.set_text(f"{lead} · {how}" if how else lead)

    def on_pam_switch(self, _sw, want_on):
        if self._pam_syncing:
            return False
        if not want_on and not self.confirm(
                "Turn off fingerprint for login and sudo?",
                "Login, sudo and admin prompts will ask for your password only. Your enrolled "
                "fingerprints are kept, and you can turn this back on at any time.", "Turn off"):
            self.show_pam(self.status.get("pam", {}))
            return True
        op = "enable" if want_on else "disable"

        def done(res, err):
            if err:
                self.refresh(lambda: self.error(err))
            else:
                word = "on" if op == "enable" else "off"
                self.refresh(lambda: self.message(f"Fingerprint for login and sudo is now {word}."))
        self.run_job("pam", done, op=op)
        return True                       # the switch follows the real state after refresh

    def after_job(self, title):
        def done(res, err):
            if err:
                self.refresh(lambda: self.error(err))
                return
            parts = []
            if res.get("output"):
                parts.append(summarise(res["output"]))
            if res.get("deleted") not in (None, [], 0):
                n = res["deleted"] if isinstance(res["deleted"], int) else len(res["deleted"])
                parts.append(f"Deleted {n} template(s) from the sensor.")
            if res.get("left"):
                parts.append(f"{res['left']} template(s) could not be deleted.")
            if res.get("moved"):
                head, sep, tail = res["moved"][0].partition("/removed-fingerprints/")
                folder = f"{head}{sep}{tail.split('/')[0]}/" if sep \
                    else os.path.dirname(res["moved"][0]) + "/"
                parts.append(f"Moved {len(res['moved'])} record(s) aside.")
                extra = f"\n\nMoved to {folder}"
            else:
                extra = ""
            summary = " ".join(p for p in parts if p) or "Done."
            summary = summary.replace(os.path.expanduser("~") + "/", "~/")
            first = title.split()[0].lower()
            text = summary if summary.lower().startswith(first) else f"{title}: {summary}"
            self.refresh(lambda: self.message(text,
                                              details=(res.get("output") or "") + extra or None))
        return done

    # ── actions ──
    def on_test(self, _btn, rec=None):
        """Test one finger (the selected one) or any of yours, as login does,
        and show which finger matched.

        The helper asks the sensor directly: fprintd only reports match / no
        match when it checks all fingers, never which finger it was."""
        me = self.status["user"]
        if rec is not None:
            picked = [[rec["user"], rec["name"], rec["enrolled"], "", rec["finger"], 1]]
        else:
            picked = [r for r in self._selected_recs() if r[0] == me and r[5]]
        finger = picked[0][4] if picked else None
        what = picked[0][1] if picked else "any of your fingers (as login and sudo do)"

        d = Gtk.Dialog(title="Test fingerprint", transient_for=self, modal=True)
        d.set_default_size(420, -1)
        close_btn = d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        again_btn = d.add_button("Test again", 1)
        again_btn.set_no_show_all(True)
        area = d.get_content_area()
        area.set_spacing(8)
        area.set_border_width(18)
        icon = Gtk.Label()
        head = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        sub = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, selectable=True)
        for w in (icon, head, sub):
            area.pack_start(w, False, False, 0)
        state = {"proc": None}

        def show(symbol, colour, title, detail):
            span = f' foreground="{colour}"' if colour else ""
            icon.set_markup(f'<span size="48000"{span}>{symbol}</span>')
            head.set_markup(f'<span size="x-large" weight="bold"{span}>'
                            f'{GLib.markup_escape_text(title)}</span>')
            sub.set_text(detail)

        def start():
            show("☝", None, "Touch the fingerprint sensor", f"Testing: {what}")
            close_btn.set_label("Cancel")
            again_btn.hide()
            state["running"] = True
            self.busy = True
            self._update_buttons()

            def work():
                try:
                    res, err = self.helper.call("test", finger=finger), None
                except Exception as e:
                    res, err = None, str(e)
                GLib.idle_add(finished, res, err)

            threading.Thread(target=work, daemon=True).start()

        def finished(res, err):
            state["running"] = False
            self.busy = False
            self._update_buttons()
            if state.get("closed"):
                return False
            result = (res or {}).get("result")
            if result == "match":
                show("✓", "#26a269", f"Match — {res['name']}", f"Tested: {what}")
            elif result == "no-match":
                show("✗", "#c01c28", "No match",
                     f"Tested: {what}\nThat finger didn't match. Try again, or test another finger.")
            elif result == "timeout":
                show("!", "#e5a50a", "No touch", "Nothing touched the sensor within 60 seconds.")
            elif result == "retry":
                show("!", "#e5a50a", "Couldn't read your finger",
                     f"{res.get('message') or ''}\nTouch the sensor flat and try again.".strip())
            elif result == "cancelled":
                return False
            else:
                show("!", "#e5a50a", "Test did not complete", err or "Unknown result")
            close_btn.set_label("Close")
            again_btn.show()
            return False

        d.show_all()
        start()
        while True:
            r = d.run()
            if r == 1 and not state.get("running"):
                start()
                continue
            break
        state["closed"] = True
        if state.get("running"):
            self.helper.cancel()
        d.destroy()

    def on_enrol(self, _btn):
        """Enrol a new finger for the user with fprintd-enroll, with progress."""
        if not shutil.which("fprintd-enroll"):
            return self.message("fprintd-enroll is not installed.", Gtk.MessageType.ERROR)
        st = self.status
        mine = {r["name"] for r in st["records"] if r["user"] == st["user"]}
        free = [f for f in FINGERS if f not in mine]
        others = [t for t in st["templates"] if not t["used_by"]]
        # fprintd's first touch is a duplicate check, then the driver's stages.
        total = (st.get("enroll_stages") or 0) + 1

        d = Gtk.Dialog(title="Enrol a finger", transient_for=self, modal=True)
        d.set_default_size(440, -1)
        close_btn = d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        start_btn = d.add_button("Start", 1)
        start_btn.get_style_context().add_class("suggested-action")
        area = d.get_content_area()
        area.set_spacing(10)
        area.set_border_width(18)

        pick = Gtk.Box(spacing=8)
        pick.pack_start(Gtk.Label(label="Finger:"), False, False, 0)
        combo = Gtk.ComboBoxText()
        for f in free:
            combo.append_text(f)
        combo.set_active(0)
        pick.pack_start(combo, True, True, 0)
        area.pack_start(pick, False, False, 0)

        warn = ("If this finger is already enrolled on another Linux install or in Windows "
                "Hello, enrolling it here deletes it from the sensor, so it stops working "
                "there. To use the same finger on several installs, enrol it once and use "
                "Export / Import.")
        if others:
            warn = (f"The sensor has {len(others)} template(s) not used by this install — "
                    "possibly another install or Windows Hello.\n\n" + warn)
        else:
            warn += "\n\nThere are no other templates on the sensor right now."
        note = Gtk.Label(label=warn, wrap=True, xalign=0, max_width_chars=55)
        area.pack_start(note, False, False, 0)

        icon = Gtk.Label()
        head = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        sub = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        bar = Gtk.ProgressBar(show_text=True)
        for w in (icon, head, sub, bar):
            w.set_no_show_all(True)
            area.pack_start(w, False, False, 0)
        state = {"proc": None, "done": False, "count": 0, "finger": None}

        def show(symbol, colour, title, detail=""):
            span = f' foreground="{colour}"' if colour else ""
            icon.set_markup(f'<span size="40000"{span}>{symbol}</span>')
            head.set_markup(f'<span size="large" weight="bold"{span}>'
                            f'{GLib.markup_escape_text(title)}</span>')
            sub.set_text(detail)
            for w in (icon, head, sub):
                w.show()

        def progress():
            n = min(state["count"], total)
            bar.set_fraction(n / total if total > 1 else 0)
            bar.set_text(f"{n} of {total} touches" if total > 1 else "")
            bar.show()

        def start():
            finger = combo.get_active_text()
            if not finger:
                return
            state.update(finger=finger, count=0)
            pick.hide()
            note.hide()
            start_btn.hide()
            show("☝", None, f"Touch the sensor with your {finger.replace('-', ' ')}",
                 "Lift your finger and touch again each time, moving it slightly.")
            progress()
            proc = subprocess.Popen(["fprintd-enroll", "-f", finger], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            state["proc"] = proc

            def read():
                for line in proc.stdout:
                    GLib.idle_add(on_line, line.strip())
                proc.wait()
                GLib.idle_add(on_exit, proc.returncode)

            threading.Thread(target=read, daemon=True).start()

        def finish(symbol, colour, title, detail):
            state["done"] = True
            show(symbol, colour, title, detail)
            if symbol != "✓":
                bar.hide()
            close_btn.set_label("Close")

        def on_line(line):
            if state["done"]:
                return False
            res = line.split(":", 1)[1].strip() if line.startswith("Enroll result:") else ""
            finger = state["finger"]
            if res == "enroll-stage-passed":
                state["count"] += 1
                progress()
                show("☝", None, "Lift and touch again", f"Enrolling: {finger}")
            elif res in ("enroll-retry-scan", "enroll-swipe-too-short",
                         "enroll-finger-not-centered", "enroll-remove-and-retry"):
                show("☝", AMBER, "That touch didn't read — touch again",
                     "Place your finger flat in the middle of the sensor.")
            elif res == "enroll-completed":
                state["count"] = total
                progress()
                finish("✓", GREEN, f"Enrolled — {finger}",
                       "If you share fingerprints with other installs, export again "
                       "so they get this finger too.")
            elif res == "enroll-duplicate":
                finish("✗", RED, "Already enrolled here",
                       "That finger is already enrolled on this install (as another finger "
                       "or for another user). Nothing was changed.")
            elif res == "enroll-data-full":
                finish("✗", RED, "The sensor is full",
                       "Delete templates you no longer need, then try again.")
            elif res:
                finish("✗", RED, "Enrolment failed", res)
            elif line.lower().startswith(("failed", "enrollstart failed", "impossible")):
                finish("✗", RED, "Enrolment could not start", line)
            return False

        def on_exit(rc):
            if not state["done"] and not state.get("closed"):
                finish("!", AMBER, "Enrolment stopped", f"fprintd-enroll exited ({rc}).")
            return False

        d.show_all()
        while True:
            r = d.run()
            if r == 1 and state["proc"] is None:
                start()
                continue
            break
        state["closed"] = True
        p = state["proc"]
        if p and p.poll() is None:
            p.terminate()
        d.destroy()
        if p:
            self.refresh()

    def on_restore(self, _btn):
        """List records moved aside and put the chosen ones back."""
        def listed(res, err):
            if err:
                return self.error(err)
            self._restore_dialog(res["records"])
        self.run_job("list_moved", listed)

    def _restore_dialog(self, recs):
        if not recs:
            return self.show_output("Nothing to restore",
                                    "No records have been moved aside on this install.")
        d = Gtk.Dialog(title="Restore fingerprint records", transient_for=self, modal=True)
        d.set_default_size(680, 380)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = d.add_button("Restore", Gtk.ResponseType.OK)
        ok.get_style_context().add_class("suggested-action")
        area = d.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.pack_start(Gtk.Label(wrap=True, xalign=0, label=(
            "Records moved aside by the boot check, this tool, or an import with --replace. "
            "Only a record whose template is still on the sensor can work, so only those "
            "can be restored.")), False, False, 0)
        # moved: date, user, finger, why, status, path, restorable
        store = Gtk.ListStore(str, str, str, str, str, str, bool)
        for r in recs:
            if not r["user_ok"]:
                status, ok_ = "✗ No such user here", False
            elif r["exists"]:
                status, ok_ = "Enrolled here again", False
            elif r["on_sensor"]:
                status, ok_ = "✓ Template on the sensor", True
            else:
                status, ok_ = "✗ Template gone", False
            why = "Replaced by import" if r["kind"] == "replaced" else "Removed"
            day, _, hms = r["date"].partition("_")       # 2026-10-25_123333
            when = f"{day} {hms[:2]}:{hms[2:4]}" if len(hms) >= 4 else day
            store.append([when, r["user"], r["name"], why, status, r["path"], ok_])
        view = self._table(store, ["Moved", "User", "Finger", "Why", "Status"])
        sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        sw.add(view)
        area.pack_start(sw, True, True, 0)

        def changed(*_):
            rows = self._selected(view, 0)
            ok.set_sensitive(bool(rows) and all(r[6] for r in rows))
        view.get_selection().connect("changed", changed)
        changed()
        d.show_all()
        rows = self._selected(view, 0) if d.run() == Gtk.ResponseType.OK else []
        paths = [r[5] for r in rows if r[6]]
        d.destroy()
        if not paths:
            return

        def done(res, err):
            if err:
                return self.refresh(lambda: self.error(err))
            text = []
            if res["restored"]:
                text.append("Restored: " + ", ".join(res["restored"]))
            if res["skipped"]:
                text.append("Not restored: " + "; ".join(res["skipped"]))
            n, k = len(res["restored"]), len(res["skipped"])
            short = f"Restored {n} record(s)." + (f" {k} not restored." if k else "")
            self.refresh(lambda: self.message(short, details="\n".join(text)))
        self.run_job("restore", done, paths=paths)

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
        rows = self._selected_recs()
        names = "\n".join(f"  • {r[1]} ({r[0]})" for r in rows)
        if self.confirm("Remove from this install only?",
                        f"{names}\n\nThese fingerprints stop working on this install. Their templates "
                        "stay on the sensor, so other installs sharing them keep working. The records "
                        "are moved to /var/lib/samsung-galaxybook/removed-fingerprints/.",
                        "Remove"):
            self.run_job("remove_records", self.after_job("Removed from this install"),
                         records=[{"user": r[0], "finger": r[4]} for r in rows])

    def on_delete_templates(self, _btn):
        rows = self._selected_tpls()
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

    def on_about(self, *_):
        st = self.status or {}
        d = Gtk.AboutDialog(transient_for=self, modal=True)
        d.set_program_name(TITLE)
        d.set_logo_icon_name(APP_ID)
        d.set_comments("Part of Samsung Galaxy Book Fixes — fingerprint-fix-sdcp.\n"
                       "Test, enrol, share and tidy fingerprints on the Galaxy Book's "
                       "Egis fingerprint sensor.\n\nAn unofficial community tool, "
                       "not made or endorsed by Samsung.")
        d.set_version("fix build " + ((st.get("marker") or "unknown").split() or ["unknown"])[0])
        d.set_authors(["David Bartlett", "Driver: Joshua Grisham, Abdallah Alkanani"])
        d.run()
        d.destroy()

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
