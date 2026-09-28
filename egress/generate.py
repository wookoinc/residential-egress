"""Generate separate, private role bundles; never read the operator's live config."""
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = '/etc/residential-egress'


def write(path, content, executable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('x', encoding='utf-8') as f:
        os.chmod(path, 0o700 if executable else 0o600)
        f.write(content)


def dump(path, value):
    write(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def openssl(*args, data=None):
    result = subprocess.run(['openssl', *args], input=data, capture_output=True)
    if result.returncode:
        raise ValueError('OpenSSL failed; install OpenSSL 1.1.1+ (Homebrew: brew install openssl@3).')
    return result.stdout


def keypair(urlsafe=False):
    key = openssl('genpkey', '-algorithm', 'X25519')
    private = openssl('pkey', '-outform', 'DER', data=key)
    public = openssl('pkey', '-pubout', '-outform', 'DER', data=key)
    # RFC 8410 PKCS#8 / SubjectPublicKeyInfo, checked before extracting raw keys.
    if private[:16].hex() != '302e020100300506032b656e04220420' or len(private) != 48:
        raise ValueError('Unsupported X25519 private key encoding')
    if public[:12].hex() != '302a300506032b656e032100' or len(public) != 44:
        raise ValueError('Unsupported X25519 public key encoding')
    encode = base64.urlsafe_b64encode if urlsafe else base64.b64encode
    return tuple(encode(k[-32:]).decode().rstrip('=') if urlsafe else encode(k[-32:]).decode()
                 for k in (private, public))


def validate(args):
    for name in ('vps', 'home_egress'):
        ip = ipaddress.ip_address(getattr(args, name))
        if ip.version != 4 or ip.is_loopback or ip.is_multicast or ip.is_unspecified:
            raise ValueError(f'{name} must be an IPv4 address, not a hostname or command')
    if args.vps == args.home_egress:
        raise ValueError('VPS and residential egress must be different IPs')
    net = ipaddress.ip_network(args.subnet, strict=True)
    private_ranges = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    if net.version != 4 or net.prefixlen != 30 or not any(net.subnet_of(n) for n in private_ranges):
        raise ValueError('subnet must be an unused RFC1918 IPv4 /30 network')
    ports = [args.hy2_port, args.reality_port, args.wg_port, args.ss_port]
    if any(p < 1 or p > 65535 for p in ports) or len(set(ports)) != len(ports):
        raise ValueError('Ports must be distinct integers between 1 and 65535')
    if not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}', args.reality_domain):
        raise ValueError('Invalid Reality TLS handshake domain')
    return net


def generate(args):
    net = validate(args)
    out = Path(args.output).expanduser().absolute()
    if out.exists() or out.is_symlink():
        raise ValueError('Output already exists; refusing to overwrite/rotate credentials. Use a new directory.')
    out.parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o077)
    temp = Path(tempfile.mkdtemp(prefix='.egress-', dir=out.parent))
    try:
        vps_priv, vps_pub = keypair()
        home_priv, home_pub = keypair()
        reality_priv, reality_pub = keypair(urlsafe=True)
        hy_pass, ss_pass, api_secret = (secrets.token_urlsafe(32) for _ in range(3))
        uid, short = str(uuid.uuid4()), secrets.token_hex(8)
        vps_wg, home_wg = str(net[1]), str(net[2])
        cert = openssl('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1',
                       '-nodes', '-days', '365', '-subj', '/CN=home-egress.invalid',
                       '-addext', 'subjectAltName=DNS:home-egress.invalid',
                       '-keyout', str(temp / 'server.key'))
        pin = hashlib.sha256(openssl('x509', '-outform', 'DER', data=cert)).hexdigest()
        wg_vps = f'[Interface]\nPrivateKey = {vps_priv}\nAddress = {vps_wg}/30\nListenPort = {args.wg_port}\nMTU = 1380\n\n[Peer]\nPublicKey = {home_pub}\nAllowedIPs = {home_wg}/32\n'
        wg_home = f'[Interface]\nPrivateKey = {home_priv}\nAddress = {home_wg}/30\nMTU = 1380\n\n[Peer]\nPublicKey = {vps_pub}\nEndpoint = {args.vps}:{args.wg_port}\nAllowedIPs = {vps_wg}/32\nPersistentKeepalive = 25\n'
        vps_config = {
            'log': {'level': 'info', 'timestamp': True},
            'inbounds': [
                {'type': 'hysteria2', 'tag': 'hy2-in', 'listen': '0.0.0.0', 'listen_port': args.hy2_port,
                 'ignore_client_bandwidth': True, 'users': [{'password': hy_pass}],
                 'tls': {'enabled': True, 'alpn': ['h3'], 'certificate_path': BASE + '/server.crt', 'key_path': BASE + '/server.key'}},
                {'type': 'vless', 'tag': 'reality-in', 'listen': '0.0.0.0', 'listen_port': args.reality_port,
                 'users': [{'uuid': uid, 'flow': 'xtls-rprx-vision'}],
                 'tls': {'enabled': True, 'server_name': args.reality_domain,
                         'reality': {'enabled': True, 'private_key': reality_priv, 'short_id': [short],
                                     'handshake': {'server': args.reality_domain, 'server_port': 443}}}}],
            'outbounds': [{'type': 'shadowsocks', 'tag': 'home-only', 'server': home_wg,
                           'server_port': args.ss_port, 'method': 'chacha20-ietf-poly1305',
                           'password': ss_pass, 'bind_interface': 're0'}],
            'route': {'final': 'home-only'}}
        home_config = {'log': {'level': 'info', 'timestamp': True},
                       'inbounds': [{'type': 'shadowsocks', 'listen': home_wg, 'listen_port': args.ss_port,
                                     'method': 'chacha20-ietf-poly1305', 'password': ss_pass}],
                       'outbounds': [{'type': 'direct', 'tag': 'residential'}],
                       'route': {'final': 'residential'}}
        client = {'mixed-port': 7897, 'allow-lan': False, 'bind-address': '127.0.0.1',
                  'mode': 'rule', 'log-level': 'info', 'ipv6': False,
                  'external-controller': '127.0.0.1:19090', 'secret': api_secret,
                  'tun': {'enable': True, 'stack': 'mixed', 'auto-route': True,
                          'auto-detect-interface': True, 'dns-hijack': ['any:53']},
                  'dns': {'enable': True, 'ipv6': False, 'enhanced-mode': 'fake-ip',
                          'fake-ip-range': '198.18.0.1/16', 'fake-ip-filter': ['*.lan', '*.local'],
                          'default-nameserver': ['223.5.5.5', '119.29.29.29'],
                          'proxy-server-nameserver': ['https://dns.alidns.com/dns-query'],
                          'nameserver': ['https://1.1.1.1/dns-query#PROXY', 'https://8.8.8.8/dns-query#PROXY'],
                          'nameserver-policy': {'geosite:cn,private': ['https://dns.alidns.com/dns-query']}},
                  'proxies': [
                      {'name': 'HOME-HY2', 'type': 'hysteria2', 'server': args.vps, 'port': args.hy2_port,
                       'password': hy_pass, 'sni': 'home-egress.invalid', 'skip-cert-verify': False,
                       'fingerprint': pin, 'alpn': ['h3']},
                      {'name': 'HOME-REALITY', 'type': 'vless', 'server': args.vps, 'port': args.reality_port,
                       'uuid': uid, 'network': 'tcp', 'tls': True, 'udp': True, 'flow': 'xtls-rprx-vision',
                       'servername': args.reality_domain, 'client-fingerprint': 'chrome',
                       'reality-opts': {'public-key': reality_pub, 'short-id': short}}],
                  'proxy-groups': [{'name': 'PROXY', 'type': 'select', 'proxies': ['HOME-HY2', 'HOME-REALITY']}],
                  'rules': [f'IP-CIDR,{args.vps}/32,DIRECT,no-resolve',
                            'DOMAIN-SUFFIX,claude.ai,PROXY', 'DOMAIN-SUFFIX,anthropic.com,PROXY',
                            'DOMAIN-SUFFIX,claudeusercontent.com,PROXY', 'GEOIP,lan,DIRECT,no-resolve',
                            'GEOSITE,private,DIRECT', 'GEOSITE,cn,DIRECT', 'GEOIP,cn,DIRECT,no-resolve', 'MATCH,PROXY']}
        deployment = str(uuid.uuid4())
        for role, cfg, wg in [('vps', vps_config, wg_vps), ('home', home_config, wg_home)]:
            dump(temp / role / 'config.json', cfg)
            write(temp / role / 're0.conf', wg)
            write(temp / role / 'install.py', (ROOT / 'egress/install.py').read_text(), True)
            write(temp / role / 'download.py', (ROOT / 'egress/download.py').read_text())
            write(temp / role / 'versions.json', (ROOT / 'versions.json').read_text())
            write(temp / role / 'setup.sh', (ROOT / 'egress/role-setup.sh').read_text(), True)
            dump(temp / role / 'bundle.json', {'schema': 1, 'id': deployment, 'role': role,
                 'vps': args.vps, 'home_egress': args.home_egress, 'subnet': str(net),
                 'vps_wg': vps_wg, 'home_wg': home_wg,
                 'ports': {'hy2': args.hy2_port, 'reality': args.reality_port, 'wg': args.wg_port, 'ss': args.ss_port}})
        write(temp / 'vps/server.crt', cert.decode())
        shutil.move(temp / 'server.key', temp / 'vps/server.key')
        dump(temp / 'client/clash.yaml', client)  # JSON is valid YAML; no YAML dependency required.
        write(temp / 'client/api-secret', api_secret + '\n')
        write(temp / 'client/setup.sh', (ROOT / 'egress/client-setup.sh').read_text(), True)
        dump(temp / 'client/expected.json', {'home_egress': args.home_egress, 'vps': args.vps, 'id': deployment})
        dump(temp / 'deployment.json', {'schema': 1, 'id': deployment, 'vps': args.vps,
             'home_egress': args.home_egress, 'subnet': str(net), 'certificate_days': 365})
        write(temp / '.gitignore', '*\n')
        # Race-safe refusal: output must still be absent at final publication.
        if out.exists() or out.is_symlink():
            raise ValueError('Output appeared during generation; refusing replacement')
        temp.rename(out)
        return out
    finally:
        if temp.exists():
            shutil.rmtree(temp)
        os.umask(old_umask)
