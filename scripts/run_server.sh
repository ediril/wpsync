#!/bin/bash

if [ $# -lt 1 ]; then
  echo "No port specified, using default 8000"
  port=8000
else
  port=$1
fi

php -S localhost:$port -t "$(dirname "$0")/../website"