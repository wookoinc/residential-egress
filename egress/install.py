#!/usr/bin/env python3
"""Self-contained fresh-install manager, copied into each private role bundle."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import socket
import subprocess
import sys
import time

try:
    from .download import download
except ImportError:
    from download import download

BASE = Path('/etc/residential-egress')
WG = Path('/etc/wireguard/re0.conf')
UNIT = Path('/etc/systemd/system/residential-egress.service')
HOME_WG = Path('/Library/LaunchDaemons/org.residential-egress.wireguard.plist')
HOME_SB = Path('/Library/LaunchDaemons/org.residential-egress.proxy.plist')


def run(*args, check=True):
    return subprocess.run([str(a) for a in args], check=check, capture_output=True, text=True)


def assert_owned(base, deployment):
    marker = base / 'installed.json'
    if base.is_symlink() or not marker.is_file() or marker.is_symlink():
        raise ValueError('No owned installation marker; refusing to change this path')
    data = json.loads(marker.read_text())
    if data.get('id') != deployment:
        raise ValueError('A different deployment owns this installation; refusing changes')
    return data


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_digest(bundle):
    h = hashlib.sha256()
    for p in sorted(bundle.iterdir()):
        if p.is_file() and p.name != '.DS_Store':
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def checked_platform(role):
    if role == 'vps':
        if platform.system() != 'Linux' or not Path('/run/systemd/system').exists():
            raise ValueError('VPS requires Ubuntu/Debian with systemd')
        release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        name, version = release.get('ID', '').strip('"'), release.get('VERSION_ID', '').strip('"')
        if (name, version) not in [('ubuntu', '22.04'), ('ubuntu', '24.04'), ('debian', '12')]:
            raise ValueError('Supported VPS systems: Ubuntu 22.04/24.04, Debian 12')
    elif platform.system() != 'Darwin' or int(platform.mac_ver()[0].split('.')[0]) < 12:
        raise ValueError('Residential node requires macOS 12+')


def paths(role):
    return [WG, UNIT] if role == 'vps' else [HOME_WG, HOME_SB]


def route_network(field):
    """Darwin prints abbreviated IPv4 networks, including 10/8 and 192.168.1."""
    address, slash, prefix = field.partition('/')
    parts = address.split('.')
    if not 1 <= len(parts) <= 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        raise ValueError('Not an IPv4 route')
    bits = int(prefix) if slash else len(parts) * 8
    return ipaddress.ip_network('.'.join(parts + ['0'] * (4 - len(parts))) + f'/{bits}', strict=False)


def preflight(meta):
    role = meta['role']
    checked_platform(role)
    for p in [BASE, *paths(role)]:
        if p.exists() or p.is_symlink():
            raise ValueError(f'Existing path collision: {p}; use status/uninstall, do not overwrite')
    for parent in (BASE.parent, WG.parent if role == 'vps' else HOME_WG.parent):
        if parent.is_symlink():
            # /etc is the standard /private/etc symlink on macOS only.
            if not (role == 'home' and parent == Path('/etc')):
                raise ValueError(f'Unexpected symlink parent: {parent}')
    specs = [(meta['ports']['hy2'], socket.SOCK_DGRAM), (meta['ports']['wg'], socket.SOCK_DGRAM),
             (meta['ports']['reality'], socket.SOCK_STREAM)] if role == 'vps' else [
                 (meta['ports']['ss'], socket.SOCK_STREAM), (meta['ports']['ss'], socket.SOCK_DGRAM)]
    for port, kind in specs:
        with socket.socket(socket.AF_INET, kind) as sock:
            try:
                sock.bind(('0.0.0.0', port))
            except OSError:
                raise ValueError(f'Port {port} already in use; generate with another port') from None
    if role == 'home':
        for binary in ('wg', 'wg-quick', 'wireguard-go'):
            if not shutil.which(binary):
                raise ValueError('Run as your normal user first: brew install wireguard-tools wireguard-go')
        mapping = Path('/var/run/wireguard/re0.name')
        if mapping.exists():
            raise ValueError('WireGuard interface alias re0 already exists')
        routes = run('netstat', '-rn', '-f', 'inet').stdout
        net = ipaddress.ip_network(meta['subnet'])
        for line in routes.splitlines():
            field = line.split()[0] if line.split() else ''
            try:
                candidate = route_network(field)
            except ValueError:
                continue
            # Ordinary default route is fine; split defaults inserted by a TUN are not.
            if candidate.prefixlen and candidate.overlaps(net):
                raise ValueError(f'Existing route overlaps {net}; choose another --subnet')
        for target in ('1.1.1.1', meta['vps']):
            route = run('route', '-n', 'get', target).stdout
            if any('interface:' in line and 'utun' in line for line in route.splitlines()):
                raise ValueError('Residential Mac has an active TUN/default VPN route; disable it before installation')
    else:
        if run('ip', 'link', 'show', 're0', check=False).returncode == 0:
            raise ValueError('WireGuard interface re0 already exists')
        for route in json.loads(run('ip', '-j', 'route', 'show').stdout):
            dst = route.get('dst', 'default')
            if dst != 'default' and ipaddress.ip_network(dst, strict=False).overlaps(ipaddress.ip_network(meta['subnet'])):
                raise ValueError('Existing route overlaps selected subnet; choose another --subnet')


def owned_write(path, content, mode=0o600):
    with path.open('xb') as f:
        os.chmod(path, mode)
        f.write(content if isinstance(content, bytes) else content.encode())


def service_files(meta):
    if meta['role'] == 'vps':
        return {UNIT: '''[Unit]
Description=Residential egress HY2 and Reality
Wants=network-online.target
After=network-online.target wg-quick@re0.service
Requires=wg-quick@re0.service
[Service]
DynamicUser=yes
SupplementaryGroups=residential-egress
ExecStart=/etc/residential-egress/sing-box run -c /etc/residential-egress/config.json
Restart=on-failure
RestartSec=5
AmbientCapabilities=CAP_NET_BIND_SERVICE CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_NET_RAW
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
LimitNOFILE=65536
[Install]
WantedBy=multi-user.target
'''.encode()}
    env = {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           'WG_QUICK_USERSPACE_IMPLEMENTATION': shutil.which('wireguard-go')}
    def plist(label, arguments):
        return plistlib.dumps({'Label': label, 'ProgramArguments': arguments,
                              'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
                              'EnvironmentVariables': env,
                              'StandardOutPath': str(BASE / 'service.log'),
                              'StandardErrorPath': str(BASE / 'service.log')})
    return {HOME_WG: plist('org.residential-egress.wireguard', ['/bin/bash', str(BASE / 'wg-supervise.sh')]),
            HOME_SB: plist('org.residential-egress.proxy', [str(BASE / 'sing-box'), 'run', '-c', str(BASE / 'config.json')])}


def address_ready(address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((address, 0))
            return True
        except OSError:
            return False


def start(meta):
    role = meta['role']
    if role == 'vps':
        run('systemctl', 'daemon-reload')
        run('systemctl', 'enable', '--now', 'wg-quick@re0.service')
        run('systemctl', 'enable', '--now', 'residential-egress.service')
        time.sleep(2)
        for unit in ('wg-quick@re0.service', 'residential-egress.service'):
            run('systemctl', 'is-active', '--quiet', unit)
    else:
        run('launchctl', 'bootstrap', 'system', HOME_WG)
        # Wait for WG local address; a remote handshake may follow after VPS is installed.
        for _ in range(20):
            if Path('/var/run/wireguard/re0.name').exists() and address_ready(meta['home_wg']):
                break
            time.sleep(1)
        else:
            raise ValueError('WireGuard did not start; inspect the saved installation bundle and system log')
        run('launchctl', 'bootstrap', 'system', HOME_SB)
        time.sleep(2)
        output = run('launchctl', 'print', 'system/org.residential-egress.proxy').stdout
        if 'state = running' not in output:
            raise ValueError('Residential sing-box did not remain running')


def stop(role):
    if role == 'vps':
        run('systemctl', 'disable', '--now', 'residential-egress.service', check=False)
        run('systemctl', 'disable', '--now', 'wg-quick@re0.service', check=False)
        for unit in ('residential-egress.service', 'wg-quick@re0.service'):
            state = run('systemctl', 'show', unit, '--property=ActiveState,MainPID')
            values = dict(line.split('=', 1) for line in state.stdout.splitlines() if '=' in line)
            if values.get('ActiveState') not in ('inactive', 'failed') or values.get('MainPID') != '0':
                raise ValueError('Service did not stop; preserving all recovery files. Stop it manually and retry uninstall.')
        if run('ip', 'link', 'show', 're0', check=False).returncode == 0:
            raise ValueError('WG interface still exists; preserving recovery files')
    else:
        for label in ('proxy', 'wireguard'):
            run('launchctl', 'bootout', f'system/org.residential-egress.{label}', check=False)
        if (BASE / 're0.conf').exists():
            run('wg-quick', 'down', BASE / 're0.conf', check=False)
        for label in ('proxy', 'wireguard'):
            if run('launchctl', 'print', f'system/org.residential-egress.{label}', check=False).returncode == 0:
                raise ValueError('launchd service still loaded; preserving recovery files. Stop it manually and retry uninstall.')
        mapping = Path('/var/run/wireguard/re0.name')
        if mapping.exists() and run('wg', 'show', mapping.read_text().strip(), check=False).returncode == 0:
            raise ValueError('WG interface still running; preserving recovery files')


def install(bundle, meta):
    if BASE.exists() or BASE.is_symlink():
        old = assert_owned(BASE, meta['id'])
        if old.get('bundle_sha256') != bundle_digest(bundle):
            raise ValueError('Bundle changed; in-place upgrades are not supported. Preserve old bundle and uninstall first.')
        print('This exact bundle is already installed. Run status to check runtime health.')
        return
    preflight(meta)
    if meta['role'] == 'vps':
        for binary in ('wg', 'wg-quick', 'curl'):
            if not shutil.which(binary):
                raise ValueError('Install prerequisites: sudo apt-get update && sudo apt-get install -y wireguard-tools curl python3')
    created = []
    started = False
    BASE.mkdir(mode=0o700)
    try:
        for name in ('config.json', 're0.conf', 'server.crt', 'server.key'):
            src = bundle / name
            if src.is_file():
                owned_write(BASE / name, src.read_bytes())
        download(BASE / 'sing-box', bundle / 'versions.json')
        run(BASE / 'sing-box', 'check', '-c', BASE / 'config.json')
        if meta['role'] == 'vps':
            run('groupadd', '--system', '--force', 'residential-egress')
            import grp
            gid = grp.getgrnam('residential-egress').gr_gid
            os.chown(BASE, 0, gid)
            os.chmod(BASE, 0o750)
            for name in ('config.json', 'server.crt', 'server.key'):
                os.chown(BASE / name, 0, gid)
                os.chmod(BASE / name, 0o640)
            WG.parent.mkdir(mode=0o700, exist_ok=True)
            owned_write(WG, (BASE / 're0.conf').read_bytes())
            created.append(WG)
        else:
            # wg-quick on macOS records the actual utun device in this name file.
            owned_write(BASE / 'wg-supervise.sh', '''#!/bin/bash
set -u
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
trap 'wg-quick down /etc/residential-egress/re0.conf >/dev/null 2>&1; exit 0' TERM INT
while true; do
  iface="$(cat /var/run/wireguard/re0.name 2>/dev/null || true)"
  if [ -z "$iface" ] || ! wg show "$iface" >/dev/null 2>&1; then
    wg-quick up /etc/residential-egress/re0.conf || true
  fi
  sleep 10 & wait $!
done
''', 0o700)
        for path, content in service_files(meta).items():
            owned_write(path, content, 0o644)
            created.append(path)
        installed = {'id': meta['id'], 'role': meta['role'], 'bundle_sha256': bundle_digest(bundle),
                     'files': {str(p): digest(p) for p in created}}
        owned_write(BASE / 'installed.json', json.dumps(installed, indent=2))
        started = True
        start(meta)
    except BaseException:
        if started:
            stop(meta['role'])
        for p in reversed(created):
            p.unlink(missing_ok=True)
        shutil.rmtree(BASE)
        if meta['role'] == 'vps':
            run('systemctl', 'daemon-reload', check=False)
        raise
    print('Installed and local services started. End-to-end egress is NOT yet verified; follow README acceptance checks.')
    if meta['role'] == 'vps':
        print('Cloud AND host firewall must allow TCP {reality}, UDP {hy2}, UDP {wg}. No firewall was changed.'.format(**meta['ports']))


def uninstall(meta):
    owned = assert_owned(BASE, meta['id'])
    allowed = {str(p) for p in paths(meta['role'])}
    for name, old_digest in owned['files'].items():
        p = Path(name)
        if name not in allowed or p.is_symlink() or (p.exists() and digest(p) != old_digest):
            raise ValueError(f'Owned file was modified: {p}; inspect manually before uninstalling')
    stop(meta['role'])
    for name in owned['files']:
        Path(name).unlink(missing_ok=True)
    shutil.rmtree(BASE)
    if meta['role'] == 'vps':
        run('systemctl', 'daemon-reload')
    print('Removed this deployment. Dependencies, system group and firewall settings were retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'install', 'status', 'uninstall'])
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    meta = json.loads((bundle / 'bundle.json').read_text())
    # sudo may discard Homebrew from PATH. Do not execute arbitrary shell snippets.
    os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    if args.action == 'plan':
        print(json.dumps({'role': meta['role'], 'paths': [str(BASE), *map(str, paths(meta['role']))],
                          'ports': meta['ports'], 'changes_firewall': False}, indent=2))
        return
    if os.geteuid() != 0:
        raise ValueError('Run this command in a terminal with sudo')
    checked_platform(meta['role'])
    if args.action == 'install':
        install(bundle, meta)
    elif args.action == 'uninstall':
        uninstall(meta)
    else:
        assert_owned(BASE, meta['id'])
        if meta['role'] == 'vps':
            print(run('systemctl', 'is-active', 'wg-quick@re0.service', 'residential-egress.service', check=False).stdout.strip())
            print(run('wg', 'show', 're0', 'latest-handshakes').stdout.strip())
        else:
            for label in ('wireguard', 'proxy'):
                r = run('launchctl', 'print', f'system/org.residential-egress.{label}', check=False)
                print(f'{label}: ' + ('RUNNING' if r.returncode == 0 and 'state = running' in r.stdout else 'UNKNOWN/STOPPED'))
            mapping = Path('/var/run/wireguard/re0.name')
            if mapping.exists():
                print(run('wg', 'show', mapping.read_text().strip(), 'latest-handshakes', check=False).stdout.strip())
        print('Handshake is a Unix timestamp (0 means never); this is not an egress acceptance test.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Do not print subprocess stdout/stderr, which could contain config secrets.
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
