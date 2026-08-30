#!/bin/bash
set -e
# Railway handles restarts; signals go directly to the cookie-free worker.
exec python worker.py
