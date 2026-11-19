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

  while IFS= read -r pid; do
    cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
    printf '  PID %s working directory: %s\n' "$pid" "${cwd:-unavailable}" >&2
  done < <(printf '%s\n' "$taken" | awk 'NR > 1 && !seen[$2]++ { print $2 }')

  exit 1
fi

php -S localhost:$port -t "$(dirname "$0")/../website"