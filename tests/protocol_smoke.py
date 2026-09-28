#!/usr/bin/env python3
"""Opt-in real protocol test using only disposable loopback processes; no TUN or system services."""
import argparse
import copy
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'residential-egress-isolated-test\n'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sing-box', required=True)
    parser.add_argument('--mihomo', required=True)
    args = parser.parse_args()
    processes, handles = [], []
    with tempfile.TemporaryDirectory(prefix='egress-protocol-') as td:
        tmp = Path(td)
        def spawn(command, label):
            log = (tmp / (label + '.log')).open('w')
            handles.append(log)
            proc = subprocess.Popen(command, stdout=log, stderr=log)
            processes.append(proc)
            return proc

        def terminate(proc):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            bundle = tmp / 'bundle'
            command = [sys.executable, str(ROOT / 'manage.py'), 'init', '--vps', '203.0.113.10',
                       '--home-egress', '198.51.100.20', '--output', str(bundle),
                       '--hy2-port', str(port()), '--reality-port', str(port()), '--ss-port', str(port())]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            home = json.loads((bundle / 'home/config.json').read_text())
            vps = json.loads((bundle / 'vps/config.json').read_text())
            home['inbounds'][0]['listen'] = '127.0.0.1'
            for inbound in vps['inbounds']:
                inbound['listen'] = '127.0.0.1'
            for name, filename in [('certificate_path', 'server.crt'), ('key_path', 'server.key')]:
                vps['inbounds'][0]['tls'][name] = str(bundle / 'vps' / filename)
            vps['outbounds'][0]['server'] = '127.0.0.1'
            vps['outbounds'][0].pop('bind_interface')  # WG unavailable in this intentionally unprivileged test.
            for role, config in [('home', home), ('vps', vps)]:
                file = tmp / (role + '.json')
                file.write_text(json.dumps(config))
                subprocess.run([args.sing_box, 'check', '-c', str(file)], check=True, capture_output=True)
            home_proc = spawn([args.sing_box, 'run', '-c', str(tmp / 'home.json')], 'home')
            vps_proc = spawn([args.sing_box, 'run', '-c', str(tmp / 'vps.json')], 'vps')
            time.sleep(0.5)
            client = json.loads((bundle / 'client/clash.yaml').read_text())
            client['tun'] = {'enable': False}
            client['dns'] = {'enable': False}
            client['rules'] = ['MATCH,PROXY']
            client['external-controller'] = ''
            for node in client['proxies']:
                node['server'] = '127.0.0.1'

            def probe(label, protocol=0, mutate=None, expect=True):
                cfg = copy.deepcopy(client)
                cfg['mixed-port'] = port()
                cfg['proxy-groups'][0]['proxies'] = [cfg['proxies'][protocol]['name']]
                if mutate:
                    mutate(cfg)
                folder = tmp / label
                folder.mkdir()
                file = folder / 'client.json'
                file.write_text(json.dumps(cfg))
                result = subprocess.run([args.mihomo, '-t', '-d', str(folder), '-f', str(file)], capture_output=True)
                assert result.returncode == 0, f'{label}: mihomo config validation failed'
                proc = spawn([args.mihomo, '-d', str(folder), '-f', str(file)], label)
                try:
                    for _ in range(50):
                        try:
                            with socket.create_connection(('127.0.0.1', cfg['mixed-port']), timeout=0.1):
                                break
                        except OSError:
                            time.sleep(0.1)
                    result = subprocess.run(['curl', '--silent', '--show-error', '--fail', '--max-time', '8',
                                             '--noproxy', '', '--proxy', f'http://127.0.0.1:{cfg["mixed-port"]}',
                                             f'http://127.0.0.1:{httpd.server_port}/'], capture_output=True)
                    passed = result.returncode == 0 and result.stdout == b'residential-egress-isolated-test\n'
                    assert passed == expect, f'{label}: expected success={expect}, curl exit={result.returncode}'
                    print(f'PASS {label}', flush=True)
                finally:
                    terminate(proc)

            probe('hy2-via-ss')
            probe('reality-via-ss', protocol=1)
            probe('wrong-pin-rejected', mutate=lambda c: c['proxies'][0].update(fingerprint='00' * 32), expect=False)
            probe('wrong-password-rejected', mutate=lambda c: c['proxies'][0].update(password='incorrect'), expect=False)
            terminate(home_proc)
            probe('hy2-backend-down-blocked', expect=False)
            probe('reality-backend-down-blocked', protocol=1, expect=False)
            home_proc = spawn([args.sing_box, 'run', '-c', str(tmp / 'home.json')], 'home-restored')
            time.sleep(0.5)
            probe('restored-hy2')
            assert vps_proc.poll() is None, 'VPS process exited unexpectedly'
        finally:
            for proc in reversed(processes):
                terminate(proc)
            for handle in handles:
                handle.close()
            httpd.shutdown()
    print('Loopback protocol smoke passed. WireGuard, launchd/systemd, public egress and TUN were not tested.')


if __name__ == '__main__':
    main()
