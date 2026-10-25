/*
 * Samsung Galaxy Book — fingerprint-fix-sdcp boot-time sensor check
 *
 * Compares fprintd's fingerprint records with the templates actually stored
 * on the sensor, and prints every record whose template is gone (typically
 * removed by Windows Hello after booting Windows with its fingerprint device
 * enabled).
 *
 * Built by install.sh against the egismoc SDCP libfprint it installs, and run
 * at boot BEFORE fprintd starts, so it has the sensor to itself.
 *
 * Output:  one line per lost fingerprint:
 *            MISSING <user> <finger-number> <record-path>
 * Exit:    0 = all records found on the sensor (or nothing enrolled)
 *          1 = at least one record has no template on the sensor
 *          2 = could not check (no sensor, open/list failed, ...)
 *
 * Second mode, used by import-fingerprint.sh (does not touch the sensor):
 *   sensor-check --set-owner USER IN OUT
 *     Reads the fprintd record IN, sets its owner to USER and writes it to
 *     OUT, so a fingerprint exported by one user can be imported for another.
 *     Exit 0 on success, 2 on error.
 *
 * Testing only (not used by the fix):
 *   FPRINT_STORE          use this folder instead of /var/lib/fprint
 *   SENSOR_CHECK_DRIVER   look for this driver instead of egismoc
 *                         (e.g. libfprint's virtual_device_storage)
 *   SENSOR_CHECK_SETTLE   milliseconds to wait after opening the sensor
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include <fprint.h>
#include <stdio.h>
#include <string.h>

static FpDevice *
find_sensor (FpContext *ctx, const char *driver)
{
  GPtrArray *devices = fp_context_get_devices (ctx);

  for (guint i = 0; devices && i < devices->len; i++)
    {
      FpDevice *dev = g_ptr_array_index (devices, i);
      if (g_strcmp0 (fp_device_get_driver (dev), driver) == 0)
        return dev;
    }
  return NULL;
}

/* Every fprintd record for this sensor: <store>/<user>/<driver>/<device-id>/<finger> */
static GPtrArray *
load_records (const char *store, const char *driver, const char *device_id)
{
  GPtrArray *records = g_ptr_array_new_with_free_func (g_object_unref);
  g_autoptr(GDir) users = g_dir_open (store, 0, NULL);
  const char *user;

  while (users && (user = g_dir_read_name (users)))
    {
      g_autofree char *dir = g_build_filename (store, user, driver, device_id, NULL);
      g_autoptr(GDir) fingers = g_dir_open (dir, 0, NULL);
      const char *finger;

      while (fingers && (finger = g_dir_read_name (fingers)))
        {
          g_autofree char *path = g_build_filename (dir, finger, NULL);
          g_autofree guchar *data = NULL;
          gsize len = 0;
          FpPrint *print;

          if (!g_file_get_contents (path, (char **) &data, &len, NULL))
            continue;
          print = fp_print_deserialize (data, len, NULL);
          if (!print)
            {
              g_printerr ("Skipping unreadable record %s\n", path);
              continue;
            }
          /* Keep where the record came from for the report */
          g_object_set_data_full (G_OBJECT (print), "user", g_strdup (user), g_free);
          g_object_set_data_full (G_OBJECT (print), "finger", g_strdup (finger), g_free);
          g_object_set_data_full (G_OBJECT (print), "path", g_strdup (path), g_free);
          g_ptr_array_add (records, print);
        }
    }
  return records;
}

/* --set-owner USER IN OUT: rewrite the username stored inside a record */
static int
set_owner (const char *user, const char *in, const char *out)
{
  g_autoptr(GError) error = NULL;
  g_autoptr(FpPrint) print = NULL;
  g_autofree guchar *data = NULL;
  g_autofree guchar *new_data = NULL;
  gsize len = 0, new_len = 0;

  if (!g_file_get_contents (in, (char **) &data, &len, &error))
    {
      g_printerr ("Cannot read %s: %s\n", in, error->message);
      return 2;
    }
  print = fp_print_deserialize (data, len, &error);
  if (!print)
    {
      g_printerr ("Not a valid fingerprint record: %s\n", in);
      return 2;
    }
  fp_print_set_username (print, user);
  if (!fp_print_serialize (print, &new_data, &new_len, &error) ||
      !g_file_set_contents (out, (const char *) new_data, new_len, &error))
    {
      g_printerr ("Cannot write %s: %s\n", out, error ? error->message : "unknown error");
      return 2;
    }
  return 0;
}

/* Default mode: compare fprintd's records with the templates on the sensor */
static int
check_sensor (void)
{
  const char *store = g_getenv ("FPRINT_STORE") ? g_getenv ("FPRINT_STORE") : "/var/lib/fprint";
  const char *driver = g_getenv ("SENSOR_CHECK_DRIVER") ? g_getenv ("SENSOR_CHECK_DRIVER") : "egismoc";
  guint settle_ms = g_getenv ("SENSOR_CHECK_SETTLE") ? (guint) g_ascii_strtoull (g_getenv ("SENSOR_CHECK_SETTLE"), NULL, 10) : 0;
  g_autoptr(FpContext) ctx = fp_context_new ();
  g_autoptr(GPtrArray) records = NULL;
  g_autoptr(GPtrArray) stored = NULL;
  g_autoptr(GError) error = NULL;
  FpDevice *dev;
  int missing = 0;

  dev = find_sensor (ctx, driver);
  if (!dev)
    {
      g_printerr ("No %s fingerprint sensor found\n", driver);
      return 2;
    }

  records = load_records (store, driver, fp_device_get_device_id (dev));
  if (records->len == 0)
    {
      g_print ("OK 0 records\n");
      return 0;            /* nothing enrolled: no need to touch the sensor */
    }

  if (!fp_device_has_feature (dev, FP_DEVICE_FEATURE_STORAGE_LIST))
    {
      g_printerr ("Driver cannot list stored templates\n");
      return 2;
    }

  if (!fp_device_open_sync (dev, NULL, &error))
    {
      g_printerr ("Could not open sensor: %s\n", error->message);
      return 2;
    }

  if (settle_ms)
    {
      gint64 until = g_get_monotonic_time () + (gint64) settle_ms * 1000;
      while (g_get_monotonic_time () < until)
        g_main_context_iteration (NULL, FALSE), g_usleep (10000);
    }

  stored = fp_device_list_prints_sync (dev, NULL, &error);
  fp_device_close_sync (dev, NULL, NULL);
  if (!stored)
    {
      g_printerr ("Could not list templates: %s\n", error ? error->message : "unknown error");
      return 2;
    }

  for (guint i = 0; i < records->len; i++)
    {
      FpPrint *record = g_ptr_array_index (records, i);
      gboolean found = FALSE;

      for (guint j = 0; j < stored->len && !found; j++)
        found = fp_print_equal (record, g_ptr_array_index (stored, j));

      if (!found)
        {
          g_print ("MISSING %s %s %s\n",
                   (const char *) g_object_get_data (G_OBJECT (record), "user"),
                   (const char *) g_object_get_data (G_OBJECT (record), "finger"),
                   (const char *) g_object_get_data (G_OBJECT (record), "path"));
          missing++;
        }
    }

  if (missing == 0)
    g_print ("OK %u records, %u templates on sensor\n", records->len, stored->len);
  return missing ? 1 : 0;
}

int
main (int argc, char **argv)
{
  if (argc >= 2 && g_strcmp0 (argv[1], "--set-owner") == 0)
    {
      if (argc != 5 || argv[2][0] == '\0')
        {
          g_printerr ("Usage: %s --set-owner USER IN OUT\n", argv[0]);
          return 2;
        }
      return set_owner (argv[2], argv[3], argv[4]);
    }
  return check_sensor ();
}
