import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'private'

    def cli(self, *extra):
        return subprocess.run([sys.executable, str(ROOT / 'manage.py'), 'init',
                               '--vps', '203.0.113.10', '--home-egress', '198.51.100.20',
                               '--output', str(self.out), *extra], capture_output=True, text=True)

    def test_generates_role_scoped_secrets_and_fail_closed_routes(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        vps = json.loads((self.out / 'vps/config.json').read_text())
        home = json.loads((self.out / 'home/config.json').read_text())
        client = json.loads((self.out / 'client/clash.yaml').read_text())
        self.assertEqual([o['type'] for o in vps['outbounds']], ['shadowsocks'])
        self.assertEqual(vps['outbounds'][0]['bind_interface'], 're0')
        self.assertEqual(client['proxy-groups'][0]['proxies'], ['HOME-HY2', 'HOME-REALITY'])
        self.assertFalse(client['proxies'][0]['skip-cert-verify'])
        self.assertNotIn(home['inbounds'][0]['password'], json.dumps(client))
        self.assertIn('AllowedIPs = 10.77.0.1/32', (self.out / 'home/re0.conf').read_text())
        self.assertNotIn('0.0.0.0/0', (self.out / 'home/re0.conf').read_text())
        self.assertEqual(os.stat(self.out).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.out / 'client/clash.yaml').st_mode & 0o777, 0o600)

    def test_repeated_init_does_not_rotate_keys(self):
        self.assertEqual(self.cli().returncode, 0)
        before = (self.out / 'vps/config.json').read_bytes()
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertEqual((self.out / 'vps/config.json').read_bytes(), before)

    def test_invalid_input_fails_before_creating_secrets(self):
        for args in [('--vps', '1.2.3.4;id'), ('--subnet', '0.0.0.0/0'),
                     ('--hy2-port', '443'), ('--reality-domain', 'evil\nExecStart=id')]:
            with self.subTest(args=args):
                self.assertNotEqual(self.cli(*args).returncode, 0)
                self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
