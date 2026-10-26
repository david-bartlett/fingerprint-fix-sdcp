#!/bin/sh

sudo systemctl stop fprintd
sudo LD_LIBRARY_PATH=/usr/local/lib/libfprint-egismoc-sdcp python3 "$(dirname "$0")/fpcheck.py"
sudo systemctl start fprintd
