"""Download a pinned, hash-verified binary, without extracting arbitrary archive paths."""
import hashlib
import json
import os
from pathlib import Path
import platform
import tarfile
import tempfile
import urllib.request


def extract_binary(archive, destination, expected):
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != expected:
        raise ValueError('Release SHA256 mismatch; no executable was installed')
    with tarfile.open(archive, 'r:gz') as tar:
        files = [m for m in tar.getmembers() if Path(m.name).name == 'sing-box']
        if len(files) != 1 or not files[0].isfile() or files[0].size > 200_000_000:
            raise ValueError('Unexpected release archive structure')
        with tar.extractfile(files[0]) as src, Path(destination).open('xb') as dst:
            dst.write(src.read())
    os.chmod(destination, 0o755)


def download(destination, versions_file):
    versions = json.loads(Path(versions_file).read_text())
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
    target = f'{platform.system().lower()}-{arch}'
    if target not in versions['sha256']:
        raise ValueError(f'Unsupported platform: {target}')
    version = versions['sing_box']
    url = f'https://github.com/SagerNet/sing-box/releases/download/v{version}/sing-box-{version}-{target}.tar.gz'
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / 'release.tgz'
        # curl uses the OS trust store on macOS, including Python installs without bundled CAs.
        import subprocess
        subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--tlsv1.2',
                        '--retry', '2', '--connect-timeout', '15', '--max-time', '300',
                        '--silent', '--show-error', '--output', str(archive), url], check=True)
        extract_binary(archive, destination, versions['sha256'][target])
