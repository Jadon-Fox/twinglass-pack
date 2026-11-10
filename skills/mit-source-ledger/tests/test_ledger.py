#!/usr/bin/env python3
"""Skill self-tests: reconstructibility, separate source identities, fail-closed quotes."""
from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
BUILDER = SKILL / 'scripts' / 'build_ledger.py'
VERIFIER = SKILL / 'scripts' / 'verify_ledger.py'
EXAMPLES = SKILL / 'examples'


class LedgerCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ['sample-a.txt', 'sample-b.txt', 'sources.example.json', 'operators.example.json']:
            (self.root / name).write_bytes((EXAMPLES / name).read_bytes())

    def build(self, operators=True):
        command = [sys.executable, str(BUILDER), '--sources', str(self.root / 'sources.example.json'),
                   '--input-root', str(self.root), '--output', str(self.root / 'packet')]
        if operators:
            command += ['--operators', str(self.root / 'operators.example.json')]
        return subprocess.run(command, text=True, capture_output=True)

    def test_custody_duplicates_and_validated_relation(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        verification = subprocess.run([sys.executable, str(VERIFIER), str(self.root / 'packet')],
                                      text=True, capture_output=True)
        self.assertEqual(verification.returncode, 0, verification.stdout)
        manifest = json.loads((self.root / 'packet' / 'manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['counts']['source_entries'], 3)
        self.assertEqual(manifest['counts']['unique_text_blobs'], 2)
        self.assertEqual(manifest['counts']['asserted_relation_records'], 1)
        sources = [json.loads(x) for x in (self.root/'packet'/'sources.jsonl').read_text().splitlines()]
        self.assertEqual(sources[0]['content_sha256'], sources[2]['content_sha256'])
        self.assertNotEqual(sources[0]['packet_source_id'], sources[2]['packet_source_id'])
        self.assertTrue((self.root/'packet.zip').is_file())

    def test_wrong_verbatim_quote_fails_closed(self):
        data = json.loads((self.root / 'operators.example.json').read_text())
        data['exact_quotes'][0]['quote'] = 'INVENTED QUOTE'
        (self.root / 'operators.example.json').write_text(json.dumps(data))
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not occur verbatim', result.stderr)

    def test_missing_relation_evidence_kept_open(self):
        data = json.loads((self.root / 'sources.example.json').read_text())
        data['relationships'][0].pop('support')
        (self.root / 'sources.example.json').write_text(json.dumps(data))
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.root / 'packet' / 'manifest.json').read_text())
        self.assertEqual(manifest['counts']['asserted_relation_records'], 0)
        self.assertEqual(manifest['counts']['open_relation_records'], 1)

    def test_tampered_blob_detected(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        blob = next((self.root / 'packet' / 'text_blobs').glob('*.txt'))
        blob.write_text('tampered')
        verification = subprocess.run([sys.executable, str(VERIFIER), str(self.root / 'packet')],
                                      text=True, capture_output=True)
        self.assertNotEqual(verification.returncode, 0)
        self.assertIn('corrupt', verification.stdout)

    def test_outside_path_rejected(self):
        data = json.loads((self.root / 'sources.example.json').read_text())
        data['sources'][0]['text_path'] = '../outside-private.txt'
        (self.root / 'sources.example.json').write_text(json.dumps(data))
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Path must remain within input root', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
