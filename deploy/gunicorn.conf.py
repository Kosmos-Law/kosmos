# Gunicorn configuration for a production Kosmos instance.
#
# scripts/install.sh --prod copies this file to the repository root (where it
# is gitignored) and the systemd unit starts gunicorn with `-c gunicorn.conf.py`.
# Edit the copy in the repository root, not this template.

import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOGS = os.path.join(_ROOT, "logs")

# Gunicorn opens its log files before Django's settings create logs/, so make
# sure the directory exists first.
os.makedirs(_LOGS, exist_ok=True)

# Socket owned by systemd socket activation (law.socket -> /run/law.sock).
# No explicit bind: activation passes the listening fd automatically.

# Number of worker processes. Two to four is right for a small firm; raise it
# through the environment rather than editing this file.
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))

# Kill and respawn a worker whose request runs past this many seconds.
timeout = 30

# Restart workers when code changes. Off in production; the dev server sets
# GUNICORN_RELOAD=1 in its unit instead.
reload = os.environ.get("GUNICORN_RELOAD") == "1"

# Send worker stdout/stderr to the error log.
capture_output = True

accesslog = os.path.join(_LOGS, "access.log")
errorlog = os.path.join(_LOGS, "error.log")
loglevel = "info"

# Gunicorn 25.1's control socket is unused here and actively harmful: it starts
# an arbiter thread whose logging can deadlock the fork of the first worker
# (master and worker wedged silently, every request a 504), and its socket
# file lands in the project root where reload=True treats it as a code change.
control_socket_disable = True
