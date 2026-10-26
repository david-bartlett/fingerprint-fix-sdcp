#!/bin/sh
sudo systemctl stop fprintd
sudo LD_LIBRARY_PATH=/usr/local/lib/libfprint-egismoc-sdcp python3 "$(dirname "$0")/fpclean.py"
sudo systemctl start fprintd
fprintd-verify
