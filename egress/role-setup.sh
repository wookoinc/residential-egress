#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
action="${1:-install}"
case "$action" in plan|install|status|uninstall) ;; *) echo 'Usage: bash setup.sh [plan|install|status|uninstall]' >&2; exit 2;; esac
if [ "$action" = install ]; then
  case "$(uname -s)" in
    Darwin)
      if [ "$(id -u)" = 0 ]; then echo 'Run bash setup.sh as your normal macOS user; it will request sudo.' >&2; exit 1; fi
      if ! command -v brew >/dev/null; then echo 'Install Homebrew from https://brew.sh first, then rerun.' >&2; exit 1; fi
      for tool in wireguard-tools wireguard-go python; do
        brew list --formula "$tool" >/dev/null 2>&1 || brew install "$tool"
      done
      ;;
    Linux)
      . /etc/os-release
      case "$ID:$VERSION_ID" in ubuntu:22.04|ubuntu:24.04|debian:12) ;; *) echo 'Requires Ubuntu 22.04/24.04 or Debian 12' >&2; exit 1;; esac
      if [ "$(id -u)" = 0 ]; then
        apt-get update
        apt-get install -y python3 curl wireguard-tools iproute2
      else
        sudo apt-get update
        sudo apt-get install -y python3 curl wireguard-tools iproute2
      fi
      ;;
    *) echo 'Unsupported OS' >&2; exit 1;;
  esac
fi
if [ "$action" = plan ] || [ "$(id -u)" = 0 ]; then
  exec python3 install.py "$action"
fi
exec sudo "$(command -v python3)" install.py "$action"
