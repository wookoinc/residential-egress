"""Read-only actual-path probe. UNKNOWN is failure, not proof of safety."""
import http.client
import ipaddress
import json
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import urlsplit


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('localhost', timeout=3)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def api(args, secret, path):
    if args.socket:
        connection = UnixHTTP(args.socket)
    else:
        url = urlsplit(args.api)
        if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('API must use a loopback HTTP address, or --socket')
        connection = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=3)
    try:
        connection.request('GET', path, headers={'Authorization': 'Bearer ' + secret})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f'Clash API returned {response.status}; use the actual runtime secret/socket')
        return json.loads(response.read())
    finally:
        connection.close()


def assess(expected, actual, connections):
    if actual != expected:
        return False, f'FAIL: egress IP does not match expected residential IP (observed {actual or "NONE"})'
    trusted = [c for c in connections if 'PROXY' in c.get('chains', []) and
               any(n in c.get('chains', []) for n in ('HOME-HY2', 'HOME-REALITY')) and
               'DIRECT' not in c.get('chains', [])]
    if not trusted:
        return False, 'UNKNOWN: no correlated residential proxy chain observed; IP alone is insufficient'
    return True, 'PASS: expected residential IP and correlated Clash proxy chain observed'


def verify(args):
    bundle = Path(args.bundle)
    expected = args.expected_ip or json.loads((bundle / 'expected.json').read_text())['home_egress']
    ipaddress.IPv4Address(expected)
    secret = Path(args.secret_file or bundle / 'api-secret').read_text().strip()
    selected = api(args, secret, '/proxies/PROXY')
    if set(selected.get('all', [])) != {'HOME-HY2', 'HOME-REALITY'}:
        raise ValueError('Runtime PROXY group differs from the generated residential-only group')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    command = ['curl', '--silent', '--show-error', '--fail', '--ipv4', '--max-time', '30',
               '--connect-timeout', '15', '--limit-rate', '4', '--local-port', str(port)]
    if args.tun:
        command += ['--noproxy', '*']
    else:
        command += ['--proxy', args.proxy, '--noproxy', '']
    command += ['https://api.ipify.org']
    observations = []
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        while process.poll() is None:
            for connection in api(args, secret, '/connections').get('connections', []):
                metadata = connection.get('metadata', {})
                if str(metadata.get('sourcePort')) == str(port):
                    observations.append({'chains': connection.get('chains'), 'rule': connection.get('rule'),
                                         'type': metadata.get('type'), 'host': metadata.get('host'),
                                         'remoteDestination': connection.get('remoteDestination')})
            time.sleep(0.15)
        stdout, _ = process.communicate()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    if process.returncode:
        print('UNKNOWN: HTTP probe failed; no egress acceptance can be claimed')
        return 1
    ok, message = assess(expected, stdout.strip(), observations)
    if args.tun and not any(c.get('type') == 'Tun' for c in observations):
        ok, message = False, 'UNKNOWN: no correlated Tun inbound observed'
    print(message)
    if observations:
        print(json.dumps(observations[-1], ensure_ascii=False))
    return 0 if ok else 1
