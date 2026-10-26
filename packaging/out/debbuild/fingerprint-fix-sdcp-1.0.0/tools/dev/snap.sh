#!/bin/sh
sudo systemctl stop fprintd
sudo LD_LIBRARY_PATH=/usr/local/lib/libfprint-egismoc-sdcp python3 "$(dirname "$0")/fpslots.py" | tee "${1:-snapshot-$(date +%H%M%S).txt}"
sudo systemctl start fprintd
