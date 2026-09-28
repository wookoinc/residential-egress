import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class DownloadTests(unittest.TestCase):
    def test_verified_archive_extracts_only_regular_binary(self):
        from egress.download import extract_binary
        with tempfile.TemporaryDirectory() as tmp:
            archive, dest = Path(tmp) / 'a.tgz', Path(tmp) / 'sing-box'
            with tarfile.open(archive, 'w:gz') as tar:
                item = tarfile.TarInfo('sing-box-1.14.2-linux-amd64/sing-box')
                item.size = 4
                tar.addfile(item, io.BytesIO(b'test'))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                extract_binary(archive, dest, '0' * 64)
            self.assertFalse(dest.exists())
            extract_binary(archive, dest, digest)
            self.assertEqual(dest.read_bytes(), b'test')

    def test_symlink_binary_is_rejected(self):
        from egress.download import extract_binary
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'a.tgz'
            with tarfile.open(archive, 'w:gz') as tar:
                item = tarfile.TarInfo('release/sing-box')
                item.type, item.linkname = tarfile.SYMTYPE, '/bin/sh'
                tar.addfile(item)
            with self.assertRaises(ValueError):
                extract_binary(archive, Path(tmp) / 'out', hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_uninstall_checks_bundle_identity(self):
        from egress.install import assert_owned
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                assert_owned(root, 'new-id')
            (root / 'installed.json').write_text(json.dumps({'id': 'existing-id'}))
            with self.assertRaises(ValueError):
                assert_owned(root, 'new-id')
            self.assertEqual(assert_owned(root, 'existing-id')['id'], 'existing-id')

    def test_macos_abbreviated_routes_are_not_skipped(self):
        from egress.install import route_network
        import ipaddress
        target = ipaddress.ip_network('192.168.1.0/30')
        self.assertTrue(route_network('192.168.1').overlaps(target))
        self.assertEqual(str(route_network('10/8')), '10.0.0.0/8')
        self.assertEqual(str(route_network('128.0/1')), '128.0.0.0/1')

    def test_uninstall_does_not_delete_files_when_stop_fails(self):
        import egress.install as installer
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'managed'
            base.mkdir()
            (base / 'installed.json').write_text(json.dumps({'id': 'test', 'files': {}}))
            with patch.object(installer, 'BASE', base), patch.object(installer, 'stop', side_effect=ValueError('still active')):
                with self.assertRaises(ValueError):
                    installer.uninstall({'id': 'test', 'role': 'home'})
            self.assertTrue((base / 'installed.json').exists())

    def test_vps_start_requires_each_service_to_be_active(self):
        from egress import install as installer
        def execute(*args, **kwargs):
            if args == ('systemctl', 'is-active', '--quiet', 'residential-egress.service'):
                raise subprocess.CalledProcessError(3, args)
            return subprocess.CompletedProcess(args, 0, '')
        with patch.object(installer, 'run', side_effect=execute), patch.object(installer.time, 'sleep'):
            with self.assertRaises(subprocess.CalledProcessError):
                installer.start({'role': 'vps'})

    def test_linux_failed_stop_preserves_recovery(self):
        from egress import install as installer
        def execute(*args, **kwargs):
            output = 'ActiveState=active\nMainPID=123\n' if args[1] == 'show' else ''
            return subprocess.CompletedProcess(args, 0, output)
        with patch.object(installer, 'run', side_effect=execute):
            with self.assertRaises(ValueError):
                installer.stop('vps')

    def test_home_waits_for_address_before_proxy(self):
        from egress import install as installer
        ready = []
        def execute(*args, **kwargs):
            if args == ('launchctl', 'bootstrap', 'system', installer.HOME_SB):
                self.assertEqual(ready, [False, True])
            return subprocess.CompletedProcess(args, 0, 'state = running')
        def check_address(address):
            ready.append(bool(ready))
            return ready[-1]
        with patch.object(installer, 'run', side_effect=execute), patch.object(installer, 'address_ready', side_effect=check_address), patch.object(installer.Path, 'exists', return_value=True), patch.object(installer.time, 'sleep'):
            installer.start({'role': 'home', 'home_wg': '10.77.0.2'})
