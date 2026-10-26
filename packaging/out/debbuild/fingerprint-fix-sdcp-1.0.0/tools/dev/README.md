# Developer tools for the sensor

Small scripts used while developing this fix. They talk to the sensor directly
through the installed driver (`/usr/local/lib/libfprint-egismoc-sdcp`), so
fingerprint-fix-sdcp must be installed. Each one stops fprintd while it runs
and starts it again afterwards. Everyday users want the Galaxy Book Fingerprint
Manager instead — it does all of this in a window.

| Script | What it does |
| --- | --- |
| `fpcheck.sh` | Read-only: the driver's features and the templates stored on the sensor |
| `snap.sh [file]` | Read-only: a text snapshot of every template on the sensor and which fprintd record uses it (`fpslots.py`), saved to `snapshot-HHMMSS.txt` or the file given — handy to compare before and after, or to paste into an issue |
| `fpclean.sh` | **Deletes** templates on the sensor that this install has no fprintd record for (another distro's or Windows Hello's are lost too), then runs `fprintd-verify` |

Run them from anywhere, as yourself (they use `sudo`):

```bash
bash tools/dev/snap.sh
```
