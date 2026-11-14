#!/bin/bash

if [ $# -lt 1 ]; then
  echo "No port specified, using default 8000"
  port=8000
else
  port=$1
fi

# PHP binds only ::1 for localhost, so it starts even when another server
# (say, one on 127.0.0.1) listens on this port, and then takes localhost from
# it. Refuse a port anything listens on.
if command -v lsof >/dev/null && taken=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN); then
  echo "Port $port is taken (pick another: $0 8008):" >&2
  echo "$taken" >&2
  exit 1
fi

php -S localhost:$port -t "$(dirname "$0")/../website"