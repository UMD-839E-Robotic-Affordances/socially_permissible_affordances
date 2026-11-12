import unittest,json,collections
from pathlib import Path
class DatasetTest(unittest.TestCase):
 def test_current_snapshot(self):
  p=Path(__file__).resolve().parents[1]/'data/current_dataset.json'
  rows=json.loads(p.read_text())
  self.assertEqual(len(rows),120)
  self.assertEqual(len({r['id'] for r in rows}),120)
  self.assertEqual(dict(collections.Counter(r['judgment'] for r in rows)),{'reject':91,'uncertain':15,'accept':14})
  self.assertTrue(all(r.get('context') and r.get('action') and r.get('object') and r.get('goal') for r in rows))
if __name__=='__main__': unittest.main()
