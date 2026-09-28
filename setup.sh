#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null; then
  echo 'Python 3.9+ required. macOS: brew install python; Ubuntu/Debian: sudo apt-get install python3' >&2
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,9), "Python 3.9+ required"'
if ! command -v openssl >/dev/null; then
  echo 'OpenSSL 1.1.1+ required. macOS: brew install openssl@3' >&2
  exit 1
fi
if command -v brew >/dev/null && [ -x "$(brew --prefix openssl@3 2>/dev/null)/bin/openssl" ]; then
  export PATH="$(brew --prefix openssl@3)/bin:$PATH"
fi
if [ "$#" -eq 0 ]; then
  exec python3 manage.py wizard
fi
exec python3 manage.py "$@"
