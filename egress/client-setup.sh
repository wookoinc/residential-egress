#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ "$(uname -s)" != Darwin ]; then echo 'Client setup supports macOS only.' >&2; exit 1; fi
if [ "$(id -u)" = 0 ]; then echo 'Run as your normal user, without sudo.' >&2; exit 1; fi
if [ ! -d '/Applications/Clash Verge.app' ]; then
  if ! command -v brew >/dev/null; then echo 'Install Homebrew from https://brew.sh, or Clash Verge Rev from https://www.clashverge.dev/ first.' >&2; exit 1; fi
  brew install --cask clash-verge-rev
fi
open -a 'Clash Verge'
open -R "$PWD/clash.yaml"
echo 'Clash Verge → Profiles/订阅 → New/新建 → Local/本地 → 选择此 clash.yaml → Activate/启用。'
echo '设置中启用服务模式、TUN 和系统代理；macOS 弹出管理员授权时自行确认。'
echo '在代理组 PROXY 中选 HOME-HY2。原有订阅不会被脚本覆盖。'
echo '启用后返回 README 执行出口验收；GUI 可能覆盖配置中的端口/API/DNS/IPv6 设置。'
