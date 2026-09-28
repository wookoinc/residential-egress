import unittest
from egress.verify import assess


class VerifyTests(unittest.TestCase):
    def test_ip_alone_is_insufficient(self):
        self.assertFalse(assess('198.51.100.20', '198.51.100.20', [])[0])

    def test_direct_chain_cannot_pass(self):
        self.assertFalse(assess('198.51.100.20', '198.51.100.20', [{'chains': ['DIRECT']}])[0])

    def test_vps_ip_cannot_pass(self):
        self.assertFalse(assess('198.51.100.20', '203.0.113.10', [{'chains': ['HOME-HY2', 'PROXY']}])[0])

    def test_actual_residential_chain_passes(self):
        self.assertTrue(assess('198.51.100.20', '198.51.100.20', [{'chains': ['HOME-HY2', 'PROXY']}])[0])
