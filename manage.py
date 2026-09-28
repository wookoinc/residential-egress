#!/usr/bin/env python3
"""Generate role bundles and verify residential egress without changing live settings."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from egress.generate import generate


def init_arguments(parser):
    parser.add_argument('--vps', required=True, help='VPS public IPv4')
    parser.add_argument('--home-egress', required=True, help='Expected residential public IPv4')
    parser.add_argument('--output', default='.private/deployment')
    parser.add_argument('--subnet', default='10.77.0.0/30', help='Unused private IPv4 /30')
    parser.add_argument('--hy2-port', type=int, default=8443)
    parser.add_argument('--reality-port', type=int, default=443)
    parser.add_argument('--wg-port', type=int, default=51820)
    parser.add_argument('--ss-port', type=int, default=8388)
    parser.add_argument('--reality-domain', default='www.microsoft.com', help='Reachable TLS 1.3 handshake server')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init_arguments(sub.add_parser('init', help='Generate fresh deployment; makes no network changes'))
    sub.add_parser('wizard', help='Interactive setup entrypoint')
    verify = sub.add_parser('verify', help='Check expected IP AND correlated live Clash connection')
    verify.add_argument('--bundle', default='.private/deployment/client')
    verify.add_argument('--proxy', default='http://127.0.0.1:7897')
    verify.add_argument('--tun', action='store_true', help='Bypass environment/system proxies, test TUN')
    verify.add_argument('--api', default='http://127.0.0.1:19090')
    verify.add_argument('--socket', help='Actual Clash UNIX control socket, if app overrides HTTP API')
    verify.add_argument('--secret-file', help='File containing actual runtime API secret')
    verify.add_argument('--expected-ip', help='Override recorded residential IPv4 after independently confirming change')
    args = parser.parse_args()
    if args.command == 'wizard':
        print('住宅出口安装向导：需要一台 VPS、一台常在线的住宅 Mac、一个 macOS 客户端。')
        print('此步骤只生成安装包；不会更改这台机器的网络。已有部署请按 README 安装，勿重新生成密钥。')
        vps = input('VPS 公网 IPv4: ').strip()
        home = input('住宅公网 IPv4（在住宅 Mac 执行 curl -4 https://api.ipify.org 获取）: ').strip()
        subnet = input('未被现有网络占用的 /30 网段 [10.77.0.0/30]: ').strip() or '10.77.0.0/30'
        args = parser.parse_args(['init', '--vps', vps, '--home-egress', home, '--subnet', subnet])
    if args.command == 'init':
        out = generate(args)
        print(f'Private deployment generated: {out}')
        print('1. Securely copy only vps/ to the VPS, run: bash setup.sh')
        print('2. Securely copy only home/ to the residential Mac, run: bash setup.sh')
        print(f'3. On this Mac run: bash "{out}/client/setup.sh"; import clash.yaml in Clash Verge.')
        print('4. Run manage.py verify; see README for firewall, TUN and recovery steps.')
    else:
        from egress.verify import verify as run_verify
        return run_verify(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError, EOFError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nCancelled.', file=sys.stderr)
        sys.exit(130)
